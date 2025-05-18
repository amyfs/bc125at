from bc125at import Scanner,clear_output
import speech_recognition as sr
import sys,time,pyaudio,io,logging,argparse,requests
from pydub import AudioSegment
from sqlalchemy.orm import Session,DeclarativeBase
from sqlalchemy import select,String,Column,Integer,create_engine
CHUNK = 2205
logger = logging.getLogger(__name__)
logging.basicConfig(filename='listener.log',
                    format='%(asctime)s %(message)s',
                    level=logging.DEBUG)
current_filename = ''

class Base(DeclarativeBase):
    pass

class Settings(Base):
    __tablename__ = 'settings'
    id = Column(Integer,primary_key=True)
    device = Column(String)

def callback(r,audio):
    print('Hit',r.energy_threshold)
    ts = time.time()
    fname = current_filename
    f = io.BytesIO(audio.get_raw_data())
    audio = AudioSegment.from_file(f,format='raw',frame_rate=44100,channels=1,sample_width=2)
    requests.post('http://localhost:5002/api/listener-hit',data=fname,files={'audio': audio.export('mp3')})
    print(f'Sent {fname}')

def run_scan(hb,device):
    global current_filename
    scan = Scanner(device,heartbeat=hb)
    prev_freq = {}
    for item in scan.endpoint():
        if prev_freq == item:
            current_filename = item
        else:
            prev_freq = item
   

def recorder(hb,settings):
    if settings == None:
        raise Exception('Settings is None')
    r = sr.Recognizer()
    m = sr.Microphone(device_index=1,chunk_size=CHUNK)
    r.pause_threshold = 2
    #r.energy_threshold = 50
    with m as source:
        r.adjust_for_ambient_noise(source)
    print('Listening...')
    stop_listening = r.listen_in_background(m,callback)
    
    try:
        run_scan(hb,settings.device)
    except Exception as e:
        logger.exception(e)
    finally:
        print('Cleaning up...')
        stop_listening(wait_for_stop=False)
        return

if __name__ == '__main__':
    engine = create_engine('sqlite:///instance/bc125at.db',echo=True)
    parser = argparse.ArgumentParser(prog='Listener',description='BC125AT to Telegram')
    parser.add_argument('-r','--remote',action='store_true',help='Enable remote control')
    args = parser.parse_args()
    settings = None
    with Session(engine) as session:
        settings = session.scalars(select(Settings)).first()
    recorder(args.remote,settings)

