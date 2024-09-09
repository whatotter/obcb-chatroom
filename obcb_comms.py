from time import sleep
import obcb
import hashlib

def text2Bin(text:str):
    return ''.join(format(byte, '08b') for byte in text.encode('ascii'))

def byte2Bin(text:bytes):
    return ''.join(format(byte, '08b') for byte in text)

def bin2Byte(binary_string):
    if len(binary_string) % 8 != 0:
        raise ValueError("Binary string length must be a multiple of 8")
    
    byte_chunks = [binary_string[i:i+8] for i in range(0, len(binary_string), 8)]
    byte_array = bytearray(int(byte, 2) for byte in byte_chunks)
    
    return byte_array

def bin2Text(binary_string, encoding='utf-8'):
    return bin2Byte(binary_string).decode(encoding)

def md5(text):
    return hashlib.md5(text.encode()).hexdigest()

ORIGINAL_PAGE = 198
class socket():
    def __init__(self, page) -> None:
        self.page = page
        self.obcbSOCK = obcb.OBCB(page)
        self.previousMsg = None

        self._subscribe()
        pass

    def recvall(self, dbg=False, timeout=None):
        timeoutTime = 0
        while True:
            if timeoutTime >= timeout:
                return None

            rdy = self.obcbSOCK.getIndexState(0)

            if rdy:
                bitScreenshot = self.obcbSOCK.getPageState()

                readsize = self.obcbSOCK.getSliceState(1, 16+1, customPageState=bitScreenshot)

                readsizeINT = int(readsize, base=2)
                readsizeBITS = readsizeINT*8

                data = self.obcbSOCK.getSliceState(18, 18+readsizeBITS, customPageState=bitScreenshot)

                try:
                    md5Hash = md5(bin2Text(data))
                    if md5Hash != self.previousMsg:
                        self.previousMsg = md5(bin2Text(data))
                        return bin2Text(data)
                    else:
                        sleep(0.01)
                        timeoutTime += 0.01
                        continue
                except:
                    print("{!} couldn't decode \"{}\"".format(data))
                    raise
            else:
                if dbg: print("not ready")

            sleep(0.01)
            timeoutTime += 0.01

    def sendall(self, text):
        # consts
        readyIndex = 0 # if this bit is high, we are ready to read
        readSizeSlice = (1,16) # size of the data being read
        dataIndex = 18 # where the data starts

        sizeBinary = format(len(text), '016b')

        if type(text) == str:
            bintext = text2Bin(text)
        else:
            bintext = byte2Bin(text)

        self.obcbSOCK.clear(0, len(bintext)+64)

        IndexPosition = 0
        for bit in sizeBinary:
            if bit == '1': self.obcbSOCK.flip(readSizeSlice[0]+IndexPosition)

            IndexPosition += 1

        IndexPosition = 0
        for bit in bintext:
            if bit == '1': self.obcbSOCK.flip(dataIndex+IndexPosition)

            IndexPosition += 1

        self.obcbSOCK.flip(readyIndex) # hopefully goes high
        self.obcbSOCK.flip(dataIndex+IndexPosition) # hopefully goes high

    def clear(self):
        self.obcbSOCK.clear(0, 32767)

    def _subscribe(self):
        self.obcbSOCK.subPartialState(self.page)

    def _unsubscribe(self):
        self.obcbSOCK.unsubPartialState()

    def _rcv(self):
        return self.obcbSOCK._recv()