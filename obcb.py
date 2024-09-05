import struct

import websocket


def valueChecks(page, startIndex, endIndex):
    if startIndex > endIndex:
        raise ValueError("startIndex must be less than endIndex")

    if startIndex < 0 or endIndex > 64**3:
        raise ValueError("startIndex and endIndex must be between 0 and 64**3")

    if page < 1 or page > 4096:
        raise ValueError("Page must be between 1 and 4096")


class OBCB:
    def __init__(self):
        """
        Connects to the OBCB WebSocket server.
        """
        self.ws = websocket.WebSocket()
        self.ws.connect("wss://bitmap-ws.alula.me/")
        self.ws.recv()  # hello (0x00)
        self.ws.recv()  # stats (0x01)

        self.offset = 0

    def pageToIndex(self, page: int) -> int:
        """
        Calculates the starting index of a given page.

        Parameters:
        - page (int): The page number.

        Returns:
        - int: The starting index of the page.
        """
        return (page - 1) * 64**3

    def rowToIndex(self, row: int) -> int:
        """
        Converts a row number to an index.

        Parameters:
        - row (int): The row number to convert.

        Returns:
        - int: The corresponding index.
        """
        return row * 60

    def indexToBytes(self, index: int) -> bytes:
        """
        Converts an index to bytes.

        Parameters:
        - index (int): The index to convert.

        Returns:
        - bytes: The converted index.
        """
        return struct.pack("<BI", 0x13, self.offset+index)

    def flip(self, page: int, index: int) -> None:
        """
        Flips the page at the specified index.

        Parameters:
        - page (int): The page number.
        - index (int): The index of the page within the book.

        Returns:
        - None
        """
        pageIndex = self.pageToIndex(page)

        bytesIndex = self.indexToBytes(pageIndex + (index+self.offset))
        self.ws.send(bytesIndex, websocket.ABNF.OPCODE_BINARY)

    def getPageState(self, page: int) -> bytes:
        """
        Retrieves the state of a page.

        Parameters:
        - page (int): The page number.

        Returns:
        - bytes: The state of the page.
        """
        self.ws.send(struct.pack("<BH", 0x10, page - 1), websocket.ABNF.OPCODE_BINARY)

        while True:
            data = self.ws.recv()

            if data[0] == 0x11:
                break

        return data[3:]

    def getIndexState(self, page: int, index: int, customPageState=None, noOffset:bool=False) -> int:
        """
        Retrieves the state of a bit at the specified index.

        Parameters:
        - page (int): The page number.
        - index (int): The index of the page within the book.

        Returns:
        - int: The state of the bit.
        """

        if customPageState == None:
            pageState = self.getPageState(page)
        else:
            pageState = customPageState

        offset = self.offset
        if noOffset: offset = 0

        byteIndex = (index+offset) // 8
        bitIndex = (index+offset) % 8

        byte = pageState[byteIndex]

        return (byte >> bitIndex) & 1
    
    def getSliceState(self, page: int, start: int, end: int, customPageState=None) -> int:
        """
        Retrieves the state of a bit(s) at the specified slice.

        Parameters:
        - page (int): The page number.
        - index (int): The index of the page within the book.

        Returns:
        - int: The state of the bit.

        fun fact: too lazy to do this properly
        """
        if customPageState == None:
            pageState = self.getPageState(page)
        else:
            pageState = customPageState

        slices = []

        for x in range(end-start):
            slices.append(
                str(
                    self.getIndexState(0, start+x, customPageState=pageState)
                    )
                ) # oh the horror

        return ''.join(slices)

    def clear(self, page: int, startIndex: int, endIndex: int) -> None:
        """
        Clears the bits in the specified range of a page.

        Parameters:
        - page (int): The page number.
        - startIndex (int): The starting index of the range.
        - endIndex (int): The ending index of the range.

        Returns:
        - None
        """
        startIndex = startIndex + self.offset
        endIndex = endIndex + self.offset
        
        valueChecks(page, startIndex, endIndex)

        pageState = self.getPageState(page)

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
                    self.flip(page, counter)

                counter += 1

                if counter > endIndex:
                    toBreak = True
                    break
