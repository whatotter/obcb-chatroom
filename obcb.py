import struct
import threading
import time
import logging
import websocket

logger = logging.getLogger(__name__)

def byte2Bin(text:bytes):
    return ''.join(format(byte, '08b') for byte in text)

def valueChecks(page, startIndex, endIndex):
    if startIndex > endIndex:
        raise ValueError("startIndex must be less than endIndex")

    if startIndex < 0 or endIndex > 64**3:
        raise ValueError("startIndex and endIndex must be between 0 and 64**3")

    if page < 1 or page > 4096:
        raise ValueError("Page must be between 1 and 4096")

def splitInto32(s):
    # List comprehension to create substrings of length 32
    return [s[i:i+32] for i in range(0, len(s), 32)]

class OBCB:
    def __init__(self, page, wsURL="wss://bitmap-ws.alula.me/"):
        """
        Connects to the OBCB WebSocket server.
        """
        self.ws = websocket.WebSocket()
        self.ws.connect(wsURL)
        self.ws.recv()  # hello (0x00)
        self.ws.recv()  # stats (0x01)

        self.data = {
            0x00: None,
            0x01: None,
            0x10: False,
            0x11: None,
            0x12: None,
            0x13: False,
            0x14: False,
            0x15: False,
        }

        self.partialStates = {}
        self.CHUNK_SIZE = 64 * 64 * 64
        self.CHUNK_SIZE_BYTES = self.CHUNK_SIZE/8
        self.UPDATE_SIZE_BYTES = 32
        self.page = page

        threading.Thread(target=self._recvManager_, daemon=True).start()
        self.fillBuffer()

        self.offset = 0

    # RX FUNCTION
    def _recv(self) -> bytes:
        """
        reserved(ish)
        """
        return self.ws.recv()
    
    # TX+RX FUNCTION
    def fillBuffer(self) -> None:
        """
        fills the `self.data` buffer to prevent null reads (view getBufferState)
        """

        pg = self.getPageState()
        pgSplit = splitInto32(pg)

        for index,value in enumerate(pgSplit):
            self.partialStates[index] = value

        return None
    
    # LOCAL FUNCTION (THREADED)
    def _recvManager_(self):
        """
        thread to manage all recieved commands
        don't run this shlawg...
        """
        while True:
            read = self._recv()
            commandByte = read[0]

            self.data[commandByte] = read

            if commandByte == 0x12:
                byteOffset, data = self._parsePartialState_(read)
                self.partialStates[(byteOffset/32)] = data

    # LOCAL FUNCTION
    def waitForCommand(self, command, pollingRate=0.01) -> bytes:
        """
        blockingly waits for a command to arrive to the buffer (self.data)

        Parameters:
        - command (int): The command to wait for (https://checkbox.ing/proto-docs/)

        Returns:
        - bytes: The packet recieved.
        """
        self.data[command] = None

        while self.data[command] == None:
            time.sleep(pollingRate)
        
        return self.data[command]

    # LOCAL FUNCTION
    def pageToIndex(self, page: int) -> int:
        """
        Calculates the starting index of a given page.

        Parameters:
        - page (int): The page number.

        Returns:
        - int: The starting index of the page.
        """
        return (page - 1) * 64**3

    # LOCAL FUNCTION
    def rowToIndex(self, row: int) -> int:
        """
        Converts a row number to an index.

        Parameters:
        - row (int): The row number to convert.

        Returns:
        - int: The corresponding index.
        """
        return row * 60

    # LOCAL FUNCTION
    def indexToBytes(self, index: int) -> bytes:
        """
        Converts an index to bytes.

        Parameters:
        - index (int): The index to convert.

        Returns:
        - bytes: The converted index.
        """
        return struct.pack("<BI", 0x13, self.offset+index)

    # TX FUNCTION
    def flip(self, index: int) -> None:
        """
        Flips the page at the specified index.

        Parameters:
        - index (int): The index of the bit within the page.

        Returns:
        - None
        """
        pageIndex = self.pageToIndex(self.page)

        bytesIndex = self.indexToBytes(pageIndex + (index+self.offset))
        self.ws.send(bytesIndex, websocket.ABNF.OPCODE_BINARY)

    # TX+RX FUNCTION
    def getPageState(self) -> bytes:
        """
        Retrieves the state of a page.

        Returns:
        - bytes: The state of the page.
        """

        self.ws.send(struct.pack("<BH", 0x10, self.page - 1), websocket.ABNF.OPCODE_BINARY)
        data = self.waitForCommand(0x11)
        return data[3:]
    
    # LOCAL FUNCTION
    def getBufferState(self) -> bytes:
        """
        compiles the partialState buffer and returns it

        note: this is horrendous, and if a certain chunk is missing, it could cause everything to go haywire
        """

        templateState = [b'' for _ in range(32767)]
        for index,data in self.partialStates.items():
            templateState[index] = data

        return b''.join(templateState)
    
    # TX FUNCTION
    def subPartialState(self, page: int) -> None:
        """
        subscribe to partial state of a page
        """

        self.ws.send(
            struct.pack("<BH", 0x14, page - 1),
            websocket.ABNF.OPCODE_BINARY
        )

    # TX FUNCTION
    def unsubPartialState(self) -> None:
        """
        unsubscribe to partial state of a page
        """

        self.ws.send(
            struct.pack("<B", 0x15),
            websocket.ABNF.OPCODE_BINARY
        )

    # RX ONLY FUNCTION
    def waitForPartialState(self) -> tuple[int, bytes]:
        """
        waits for a PartialStateUpdateMessage, then returns the parsed data

        Returns:
        - tuple: The packet's bytes offset and the data bytes, respectively.
        """

        data = self.waitForCommand(0x12)
        return self._parsePartialState_(data)
    
    # LOCAL FUNCTION
    def _parsePartialState_(self, packet:bytes) -> tuple[int, bytes]:
        """
        parses the `PartialStateUpdateMessage` (0x12) message into a tuple

        Parameters:
        - packet (bytes): the whole PartialStateUpdateMessage packet

        Returns:
        - tuple: The bytes offset and the data bytes, respectively.
        """
        pktOffset = struct.unpack('<I', packet[1:5])[0]
        chunkID = (pktOffset // self.CHUNK_SIZE_BYTES) + 1 # start at 1 instead of 0..
        byteOffset = int(pktOffset % self.CHUNK_SIZE_BYTES)

        assert chunkID == self.page

        return (byteOffset, packet[5:])

    # (TX)RX FUNCTION
    def getIndexState(self, index: int, useBuffer=True, noOffset:bool=False, customPageState=None) -> int:
        """
        Retrieves the state of a bit at the specified index.

        Parameters:
        - page (int): The page number.
        - index (int): The index of the page within the book.

        Returns:
        - int: The state of the bit.

        Notes:
        - customPageState will always override useBuffer
        """

        if customPageState == None:
            if useBuffer == False:
                pageState = self.getPageState()
            else:
                pageState = self.getBufferState()
                
        else:
            pageState = customPageState

        if len(pageState) == 0: return 0
        if index > len(pageState):
            raise IndexError("buffer does not have {} bits - has {} instead".format(index, len(pageState)))

        offset = 0 # used for debug

        byteIndex = (index+offset) // 8
        bitIndex = (index+offset) % 8
        byte = pageState[byteIndex]

        return (byte >> bitIndex) & 1
    
    # RX FUNCTION
    def getSliceState(self, start: int, end: int, useBuffer=True, customPageState=None) -> str:
        """
        Retrieves the state of bits, derived from a slice (is that how you say it?).

        Parameters:
        - start (int): The start of the slice
        - end (int): the END of the pizza slice

        Returns:
        - str: The states of each bit, as a concatinated string.

        fun fact: too lazy to do this properly
        """
        if customPageState == None:
            if useBuffer == False:
                pageState = self.getPageState()
            else:
                pageState = self.getBufferState()
        else:
            pageState = customPageState

        slices = []

        for x in range(end-start):
            istate = self.getIndexState(start+x, customPageState=pageState)

            slices.append(
                str(
                    istate
                    )
                ) # oh the horror

        return ''.join(slices)

    # TX+RX FUNCTION
    def clear(self, startIndex: int, endIndex: int) -> None:
        """
        Clears the bits in the specified range of a page.

        Parameters:
        - startIndex (int): The starting index of the range.
        - endIndex (int): The ending index of the range.

        Returns:
        - None
        """
        startIndex = startIndex + self.offset
        endIndex = endIndex + self.offset
        
        valueChecks(self.page, startIndex, endIndex)

        pageState = self.getPageState()

        toBreak = False
        skipped = 0
        counter = startIndex

        for byte in pageState:
            if toBreak:
                break

            for i in range(8):
                if skipped < startIndex:
                    skipped += 1
                    continue

                bit = (byte >> i) & 1
                if bit == 1:
                    self.flip(counter)

                counter += 1

                if counter > endIndex:
                    toBreak = True
                    break