import serial,time,requests,argparse,sqlite3
from serial.tools.list_ports import comports
from tqdm import tqdm

delay = 0.5

def clear_output(lines):
    for i in range(lines):
        print('\033[1A',end='\x1b[2K')

def char_replace(text):
    out = text.replace(b'\x81',b'UP') \
               .replace(b'\x82',b'DOWN') \
               .replace(b'\x87\x88',b'CLOSE') \
               .replace(b'\x89\x8A',b'CALL') \
               .replace(b'\x8D\x8E\x8F\x90',b'HOLD') \
               .replace(b'\x98\x99\x9A',b'AM') \
               .replace(b'\x9B\x9C\x9A',b'FM') \
               .replace(b'\x9D\x9E\x9C\x9A',b'NFM') \
               .replace(b'\xA6',b'1') \
               .replace(b'\xA7',b'2') \
               .replace(b'\xA8\xA9',b'3') \
               .replace(b'\xAA\xAB',b'4') \
               .replace(b'\xAC\xAD',b'5') \
               .replace(b'\xB5\xB6',b'CLOSE') \
               .replace(b'\xB7\xB8',b'CALL') \
               .replace(b'\xC5\xC6\xC7',b'SRC:') \
               .replace(b'\xCD\xCE\xCF',b'BNK:') \
               .replace(b'\xD4\xD5\xD6',b'SVC:') \
               .replace(b'\x92',b' ')
    return out

class Scanner:
    def __init__(self,device,heartbeat=True):
        self.ser = serial.Serial(device,115200,timeout=float(.005))
        self.hb = heartbeat
    
    def mdl_check(self):
        self.ser.flushInput()
        self.ser.write(b'MDL\r\n')
        return self.ser.readline()
    
    def enter_prg(self):
        self.ser.flushInput()
        self.ser.write(b'PRG\r\n')
        return self.ser.readline()

    def exit_prg(self):
        self.ser.flushInput()
        self.ser.write(b'EPG\r\n')
        return self.ser.readline()

    def get_banks(self):
        self.enter_prg()
        self.ser.flushInput()
        self.ser.write(b'SCG\r\n')
        output = self.parse_banks(self.ser.readline())
        self.exit_prg()
        self.keypress('H','P')
        return output
    
    def parse_banks(self,banks):
        b = banks.decode('cp850').strip().split(',')
        return [x == '0' for x in b[1]]

    def set_banks(self,banks):
        self.enter_prg()
        self.ser.flushInput()
        b = ''.join(['0' if i else '1' for i in banks])
        self.ser.write(f'SCG,{b}\r\n'.encode())
        output = self.ser.readline()
        self.exit_prg()
        self.keypress('H','P')
        return output

    def channel(self,idx,name='',frq='',mod='',ctcss='',dly='',lout='',pri=''):
        output = ''
        self.enter_prg()
        self.ser.flushInput()
        if all([i == '' for i in [name,frq,mod,ctcss,dly,lout,pri]]):
            self.ser.write(f'CIN,{idx}\r\n'.encode())
            output = self.channel_parser(self.ser.readline())
        else:
            self.ser.write(f'CIN,{idx},{name},{frq},{mod},{ctcss},{dly},{lout},{pri}\r\n' \
                    .encode())
            output = self.ser.readline()
        self.exit_prg()
        self.keypress('H','P')
        return output
    def bulk_channel(self,iterable):
        """
        Iterate over a list and make changes or retrieve channels.
        Parameter:
            iterable - a list of dicts with at least one key, 'idx'.
        Input/output keys:
            idx - index
            name - name
            frq - frequency
            mod - modulation (AUTO/AM/FM/NFM)
            ctcss - CTCSS/DCS (0-231, custom coding for BC125AT)
            dly - delay, (-10,-5,0,1,2,3,4,5)
            lout - lockout, 0 or 1
            pri - priority, 0 or 1
        """
        out = []
        self.enter_prg()
        print(iterable)
        for item in iterable:
            self.ser.flushInput()
            if 'frq' in item.keys():
                s = 'CIN,{},{},{},{},{},{},{},{}\r\n'.format(
                        item.get('idx'),
                        item.get('name',''),
                        item.get('frq',''),
                        item.get('mod',''),
                        item.get('ctcss',''),
                        item.get('dly',''),
                        item.get('lout',''),
                        item.get('pri','')
                    ).encode()
                self.ser.write(s)
                out.append(self.ser.readline())
                print(out)
            else:
                self.ser.write(f'CIN,{item["idx"]}\r\n'.encode())
                out.append(self.ser.readline())
        self.exit_prg()
        self.keypress('H','P')
        return out
    def channel_parser(self,cin):
        """
        Turn raw CIN output into pretty dict.
        Output:
        {CMD, INDEX, BANK, FRQ, MOD, CTCSS, DLY, LOUT, PRI}
        """
        c = cin.decode('cp850').split(',')
        '''
        1: 1-50
        2: 51-100
        3: 101-150
        4: 151-200
        5: 201-250
        6: 251-300
        7: 301-350
        8: 351-400
        9: 401-450
        0: 451-500
        '''
        banks = [None,
                 1 <= int(c[1]) <= 50,
                 51 <= int(c[1]) <= 100,
                 101 <= int(c[1]) <= 150,
                 151 <= int(c[1]) <= 200,
                 201 <= int(c[1]) <= 250,
                 251 <= int(c[1]) <= 300,
                 301 <= int(c[1]) <= 350,
                 351 <= int(c[1]) <= 400,
                 401 <= int(c[1]) <= 450,
                 451 <= int(c[1]) <= 500
                 ]
        return {
                    'CMD': c[0],
                    'index': c[1],
                    'bank': banks.index(True),
                    'name': c[2],
                    'frequency': c[3],
                    'modulation': c[4],
                    'ctcss': c[5],
                    'delay': c[6],
                    'locked': c[7] == '1',
                    'priority': c[8].strip() == '1'
                }
    def sts_parser(self,sts):
        '''
        ['STS', #command
        '011000', #?
        '          ¼¡    ', #signal strength indicator 
        '',  #line1 mode
        'BANK 2-13       ', #line2 
        '',  #line2 mode
        'CH063  123.9000ü', #line3 
        '', #line3 mode
        ' ÿÖÜ            ', #line4 
        '', #line4 mode 
        '                ', #line5 
        '', #line5 mode
        '═╬¤ 2   67 9 Æ  ', #line6 
        '', #line6 mode
        '0', #?
        '1', #?
        '0', #?
        '0', #?
        '', #?
        '', #?
        '0', #?
        '', #?
        '3\r'] #power?'''
        sp = char_replace(sts).decode('cp850').split(',')
        obj = {
                'CMD': sp[0],
                'L1_CHAR': sp[2],
                'L2_CHAR': sp[4],
                'L3_CHAR': sp[6],
                'L4_CHAR': sp[8],
                'L5_CHAR': sp[10],
                'L6_CHAR': sp[12],
                'PWR': sp[-1].strip()
                }
        return obj
    def sts_render(self,parsed,clear=0,ctoggle=True):
        print(parsed['L1_CHAR'],'\r\n',
              parsed['L2_CHAR'],'\r\n',
              parsed['L3_CHAR'],'\r\n',
              parsed['L4_CHAR'],'\r\n',
              parsed['L5_CHAR'],'\r\n',
              parsed['L6_CHAR'])
        if ctoggle:
            clear_output(6+clear)

    def glg_parser(self,glg):
        sp = char_replace(glg).decode('cp850').split(',')
        try:
            obj = {
                    'CMD': sp[0],
                    'FRQ': sp[1],
                    'MOD': sp[2],
                    'NAME': sp[7],
                    'SQL': sp[8],
                    'MUT': sp[9],
                    'CH_NUM': sp[11] 
                    }
        except IndexError:
            #print(sp)
            return {
                    'CMD': '',
                    'FRQ': '',
                    'MOD': '',
                    'NAME': '',
                    'SQL': '',
                    'MUT': '',
                    'CH_NUM': ''
                    }
        return obj

    def glg_reader(self):
        self.ser.flushInput()
        self.ser.write(b'GLG\r\n')
        #print('Wrote GLG')
        o = self.ser.readline()
        return o

    def sts_reader(self):
        self.ser.flushInput()
        self.ser.write(b'STS\r\n')
        o = self.ser.readline()
        return o

    def pwr_reader(self):
        self.ser.flushInput()
        self.ser.write(b'PWR\r\n')
        o = self.ser.readline()
        return o
   
    def keypress(self,key,mode):
        self.ser.flushInput()
        self.ser.write(f'KEY,{key},{mode}\r\n'.encode())
        o = self.ser.readline()
        return o
    def screen_render(self):
        try:
            while True:
                sts = self.sts_reader()
                parsed = self.sts_parser(sts)
                self.sts_render(parsed)
                time.sleep(delay)
        except KeyboardInterrupt:
            return
    def shell(self):
        try:
            while True:
                sts = self.sts_reader()
                parsed = self.sts_parser(sts)
                self.sts_render(parsed,ctoggle=False)
                a = input('>')
                if a != '' and not ',' in a:
                    print(self.keypress(a.upper(),'P'))
                elif a != '':
                    b = a.split(',')
                    print(self.keypress(a[0].upper(),a[1].upper()))
                print('--')
                clear_output(8)
                time.sleep(delay)
        except KeyboardInterrupt:
            return

    def glg_render(self):
        prev_freq = ''
        start_time = None
        count = 0
        hits = []
        try:
            while True:
                glg = self.glg_reader()
                pwr = self.pwr_reader()
                parsed = self.glg_parser(glg)
                frq = '{:0<8}'.format(int(parsed['FRQ'][1:])/10000)
                print('Freq: ',frq,'Current channel: ',parsed['NAME'])
                print('Channels tracked: ',len(hits))
                if prev_freq == parsed['FRQ']:
                    if start_time == None:
                        start_time = time.time()
                    print('Hit: ',parsed['NAME'],' Freq: ',frq,', Count: ',count)
                    count += 1
                    clear_output(3)
                else:
                    if count > 1:
                        hits.append('{:0<8} Count: {} Start: {} End: {}'.format(int(prev_freq[1:])/10000, count,start_time,time.time()))
                        count = 0
                        start_time = None
                    prev_freq = parsed['FRQ']
                    clear_output(2)
                time.sleep(delay)
        except KeyboardInterrupt:
            print('\n'.join(hits))
            return

    def to_db(self):
        con = sqlite3.connect('hits.db')
        cur = con.execute('CREATE TABLE IF NOT EXISTS hits(freq, name, time_start, time_end)')
        count = 0
        start_time = None
        end_time = None
        prev_freq = {'FRQ':''}
        try:
            while True:
                glg = self.glg_reader()
                parsed = self.glg_parser(glg)
                print('Current channel: ',parsed['NAME'].ljust(20,' '),'Freq: ',(int(parsed['FRQ'])/10000))
                if prev_freq['FRQ'] == parsed['FRQ']:
                    if start_time == None:
                        start_time = time.time()
                    count += 1
                    clear_output(1)
                else:
                    if count > 1:
                        end_time = time.time()
                        count = 0
                        cur.execute('INSERT INTO hits VALUES (?, ?, ?, ?)',(prev_freq['FRQ'],prev_freq['NAME'],start_time,end_time,))
                        con.commit()
                        start_time = None
                        print('Inserted row for ',prev_freq['NAME'])
                    else:
                        print('----')
                    prev_freq = parsed
                    clear_output(2)
                time.sleep(delay)
        except KeyboardInterrupt:
            return
    def heartbeat(self):
        try:
            r = requests.get('http://localhost:5001/heartbeat')
            j = r.json()
            return j['pending']
        except:
            return False
    def heartbeat_send(self,data):
        try:
            r = requests.post('http://localhost:5002/heartbeat',data=data)
        except:
            return
    def endpoint(self):
        while True:
            time.sleep(delay)
            glg = self.glg_reader()
            parsed = self.glg_parser(glg)
            if self.hb:
                self.heartbeat_send(parsed)
            yield parsed

def download(scan):
    con = sqlite3.connect('channels.db')
    cur = con.execute('CREATE TABLE IF NOT EXISTS channels(idx, name, bank, frq, mod, ctcss, dly, lout, pri)')
    x = scan.bulk_channel(tqdm([{'idx': x} for x in range(1,500)],desc='Getting channels from scanner...'))
    print(x[0:10]) 
    cur.executemany('INSERT INTO channels VALUES(:INDEX, :NAME, :BANK, :FRQ, :MOD, :CTCSS, :DLY, :LOUT, :PRI)',tqdm(x,desc='Writing channels to DB...'))
    con.commit()
    con.close()

def main_tui():
    q = questionary.select('Select a device: ',choices=[questionary.Choice(f'{i.manufacturer} {i.product}',value=i.device) for i in comports()]).ask()
    scan = Scanner(q,heartbeat=False)
    close = False
    while close == False:
        q = questionary.select('Choose function: ',choices=['Shell','STS loop','GLG loop','GLG to DB','Close']).ask()
        try:
            match q:
                case 'Shell':
                    scan.shell()
                case 'STS loop':
                    scan.screen_render()
                case 'GLG loop':
                    scan.glg_render()
                case 'GLG to DB':
                    scan.to_db()
                case 'Close':
                    close = True
        except KeyboardInterrupt:
            close = True

def main_cli(args):
    scan = Scanner(args.device,heartbeat=False)
    if args.export:
        download(scan)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='BC125AT')
    parser.add_argument('-t','--tui',help='Interactive user interface for the scanner.',action='store_true')
    parser.add_argument('-d','--device',help='Serial device to interact with.',choices=[i.device for i in comports()],default='/dev/ttyACM0')
    parser.add_argument('-e','--export',help='Export channels from device.',action='store_true')
    parser.add_argument('-c','--channel',help='Channel to retrieve.',type=int)
    args = parser.parse_args()
    if args.tui:
        try:
            import questionary
            main_tui()
        except:
            print('Questionary not installed, running STS loop.')
            scan = Scanner(args.device,heartbeat=False)
            scan.screen_render()
    else:
        main_cli(args)
