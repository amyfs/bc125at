import logging,io,os,json,requests,subprocess,datetime
from flask import Flask,jsonify,request,Response,render_template,redirect,make_response
from flask_sqlalchemy import SQLAlchemy
from urllib.parse import urlparse
from base64 import b64encode
from bc125at import Scanner
from serial.tools.list_ports import comports

app = Flask(__name__)

db = SQLAlchemy()

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bc125at.db'
app.config['SQLALCHEMY_ECHO'] = True

app.jinja_env.add_extension('jinja2.ext.debug')

db.init_app(app)

class Hit(db.Model):
    __tablename__ = 'hits'
    id = db.Column(db.Integer,primary_key=True)
    frequency = db.Column(db.Float)
    sys_name = db.Column(db.String)
    group_name = db.Column(db.String)
    channel_name = db.Column(db.String)
    power = db.Column(db.Integer)
    channel_num = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime)
    file = db.Column(db.LargeBinary)

class Channel(db.Model):
    __tablename__ = 'channels'
    id = db.Column(db.Integer,primary_key=True)
    index = db.Column(db.Integer)
    bank = db.Column(db.Integer)
    name = db.Column(db.String)
    frequency = db.Column(db.Float)
    modulation = db.Column(db.String)
    ctcss = db.Column(db.Integer)
    delay = db.Column(db.Integer)
    locked = db.Column(db.Boolean)
    priority = db.Column(db.Boolean)

class Settings(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer,primary_key=True)
    device = db.Column(db.String)
    name = db.Column(db.String)
    model = db.Column(db.String)
    bank_state = db.Column(db.String) #format same as on scanner
    bank_names = db.Column(db.String) #comma separated list?
    output_telegram_token = db.Column(db.String)
    output_telegram_id = db.Column(db.String)
    output_telegram_enabled = db.Column(db.Boolean)
    output_discord_hook = db.Column(db.String)
    output_discord_enabled = db.Column(db.Boolean)

curr_value = ''

logging.getLogger('werkzeug').disabled = True

def listener_start():
    subprocess.run(['sh','runner_t.sh'])
    #print('Placeholder: start listener')

def listener_stop():
    subprocess.run(['sh','runner_t.sh','k'])
    #print('Placeholder: stop listener')

def event_stream():
    prev_value = ''
    while True:
        if prev_value == curr_value:
            prev_value = curr_value
            continue
        else:
            prev_value = curr_value
            yield f'data: {curr_value} \n\n'

@app.route('/api/listener-heartbeat')
def listener_stdout():
    return Response(event_stream(),mimetype='text/event-stream')

@app.route('/channels',methods=['GET','POST'])
def channels():
    if request.method == 'GET':
        banks = db.session.execute(db.select(Channel).order_by(Channel.index.asc())).scalars()
        bank_names = db.session.execute(db.select(Settings)).scalar().bank_names.split(',')
        b = list(banks)
        if len(b) == 0:
            settings = db.session.execute(db.select(Settings)).scalar()
            listener_stop()
            scan = Scanner(settings.device)
            chans = scan.bulk_channel([{'idx': x} for x in range(1,501)])
            print('Grabbed channels from scanner, parsing')
            x = [scan.channel_parser(i) for i in chans]
            print(x)
            db.session.execute(db.insert(Channel),x)
            db.session.commit()
            listener_start()
            redirect('/channels')
        return render_template('channels.html',channels=b,bank_names=bank_names)

@app.route('/channels/<bank_id>',methods=['GET'])
def channels_bank(bank_id):
    banks = db.session.execute(db.select(Channel).where(Channel.bank == bank_id)).scalars()
    bank_name = db.session.execute(db.select(Settings)).scalar().bank_names.split(',')
    return render_template('bank_channels.html',channels=list(banks),bank_names=bank_name,bank_id=bank_id)

@app.route('/channel/<idx>',methods=['POST'])
def channel(idx):
    pth = urlparse(request.headers.get('Referer')).path
    ch = db.session.execute(db.select(Channel).where(Channel.index == idx)).scalar()
    settings = db.session.execute(db.select(Settings)).scalar()
    #update db
    ch.name = request.form.get('name',ch.name)
    ch.frequency = request.form.get('frequency',ch.frequency)
    ch.locked = request.form.get('locked',ch.locked) == 'on'
    ch.modulation = request.form.get('modulation',ch.modulation)
    ch.delay = request.form.get('delay',ch.delay)
    ch.priority = request.form.get('priority',ch.priority) == 'on'
    db.session.commit()
    #update scanner
    listener_stop()
    scan = Scanner(settings.device)
    f = request.form.get('frequency','')
    frq = '' if f == '' else str(float(f)*10000)[:-2].zfill(8)
    lout = 1 if request.form.get('locked','') == 'on' else 0 if request.form.get('locked','') == '' else 0
    pri = 1 if request.form.get('priority','') == 'on' else 0 if request.form.get('priority','') == '' else 0
    r = scan.bulk_channel([{'idx': idx, 
                        'name': request.form.get('name',''),
                        'frq': frq,
                        'mod': request.form.get('modulation',''),
                        'ctcss': request.form.get('ctcss',''),
                        'dly': request.form.get('delay',''),
                        'lout': lout,
                        'pri': pri
                        }])
    listener_start()
    return redirect(pth)

@app.route('/api/listener-hit',methods=['POST'])
def listener_hit():
    settings = db.session.execute(db.Select(Settings)).scalar()
    tg_bot_token = settings.output_telegram_token
    chat_id = settings.output_telegram_id
    audio = request.files['audio']
    audio.stream.seek(0)

    capt = Hit(
                frequency=int(request.form.get('FRQ','0'))/10000,
                channel_name=request.form.get('NAME',''),
                channel_num=int(request.form.get('CH_NUM','0')),
                timestamp=datetime.datetime.now(),
                file=audio.stream.read()
            )
    audio.stream.seek(0)
    try:
        if settings.output_telegram_enabled:
            r = requests.post(f'https://api.telegram.org/bot{tg_bot_token}/sendAudio',
                                data={'chat_id':chat_id,'caption':f'{capt.channel_name} {capt.frequency}'},
                                files={'audio': audio})
        audio.stream.seek(0)
        if settings.output_discord_enabled:
            rd = requests.post(settings.output_discord_hook,
                                files={'audio': ('audio.mp3',audio,'audio/mpeg')},
                                data={'content': f'{capt.channel_name} {capt.frequency}' 
                                      })
            #print(r.status_code,r.text)
    except requests.exceptions.ConnectionError:
        print('Caught ConnectionError, saving to DB.')
    db.session.add(capt)
    db.session.commit()
    return jsonify(r.json())


@app.route('/hits')
def hits():
    res = db.paginate(db.select(Hit).order_by(Hit.id.desc()),per_page=13)
    audio = [b64encode(i.file).decode('ascii') for i in res.items]
    return render_template('hits.html',entries=res,audio=audio)

@app.route('/heartbeat',methods=['POST'])
def heartbeat():
    global curr_value
    curr_value = request.form['NAME']
    return jsonify({})

@app.route('/settings',methods=['GET','POST'])
def settings():
    res = db.session.execute(db.select(Settings)).scalar()
    cp = comports()
    if request.method == 'GET':
        if res == None:
            listener_stop()
            scan = Scanner(cp[0].device)
            bnks = scan.get_banks()
            listener_start()
            settings = Settings(
                        device=cp[0].device,
                        name='',
                        model=cp[0].description,
                        bank_state = ''.join(['1' if x else '0' for x in bnks]),
                        bank_names = ','.join([f'Bank {i+1}' for i,_ in enumerate(bnks)]),
                        output_telegram_token = '',
                        output_telegram_id = '',
                        output_telegram_enabled = False,
                        output_discord_hook = '',
                        output_discord_enabled = False
                    )
            db.session.add(settings)
            db.session.commit()
        else:
            settings = res
    else:
        print(request.form)
        bank_names = []
        bank_state = []
        for i in range(10):
            bank_names.append(request.form[f'bank_{i}_name'])
            bank_state.append(request.form.get(f'bank_{i}_enabled','off') == 'on')
        print(bank_names,bank_state)
        res.device = request.form['device_selector']
        res.name = request.form['device_name']
        res.model = request.form['device_model']

        res.bank_state = ''.join(['1' if x else '0' for x in bank_state])
        res.bank_names = ','.join(bank_names)
        res.output_telegram_token = request.form['output_telegram_token']
        res.output_telegram_id = request.form['output_telegram_id']
        res.output_telegram_enabled = request.form.get('output_telegram_enabled','off') == 'on'
        res.output_discord_hook = request.form['output_discord_hook']
        res.output_discord_enabled = request.form.get('output_discord_enabled','off') == 'on'
        db.session.commit()
    
        listener_stop()
        scan = Scanner(res.device)
        scan.set_banks(bank_state)
        listener_start()
        settings = res

    return render_template('device.html',serial_devices=cp,settings=settings)

@app.route('/')
def root():
    hits = list(db.session.execute(db.select(Hit).order_by(Hit.id.desc()).limit(5)).scalars())
    chans = list(db.session.execute(db.select(Channel).filter(Channel.index.in_([x.channel_num for x in hits]))).scalars())
    if len(chans) == 0:
        redirect('/settings')
    audio = [b64encode(i.file).decode('ascii') for i in hits]
    return render_template('index.html',channels=chans,hits=hits,audio=audio)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print(db)
    try:
        listener_start()
        app.run(host='0.0.0.0',port=5002)
    except Exception as e:
        raise(e)
    finally:
        pass
        listener_stop()
