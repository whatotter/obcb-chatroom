import time
import obcb

a = obcb.OBCB()

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

ORIGINAL_PAGE = 198
class socket():
    def __init__(self, page) -> None:
        self.page = page
        pass

    def recvall(self, dbg=False):
        while True:
            pg = a.getPageState(self.page)

            if len(pg) != 32768:
                continue # didn't get full page state, retry

            break

        rdy = a.getIndexState(self.page, 0, customPageState=pg)

        if rdy:
            readsize = a.getSliceState(self.page, 1, 16+1, customPageState=pg)

            readsizeINT = int(readsize, base=2)
            readsizeBITS = readsizeINT*8

            dataread = a.getSliceState(self.page, 18, 18+readsizeBITS, customPageState=pg)

            try:
                return bin2Text(dataread)
            except:
                pass # couldn't decode
        else:
            if dbg: print("not ready")

        time.sleep(0.1)

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

        a.clear(self.page, 0, len(bintext)+64)

        IndexPosition = 0
        for bit in sizeBinary:
            if bit == '1': a.flip(self.page, readSizeSlice[0]+IndexPosition)

            IndexPosition += 1

        IndexPosition = 0
        for bit in bintext:
            if bit == '1': a.flip(self.page, dataIndex+IndexPosition)

            IndexPosition += 1

        a.flip(self.page, readyIndex) # hopefully goes high
        a.flip(self.page, dataIndex+IndexPosition) # hopefully goes high
