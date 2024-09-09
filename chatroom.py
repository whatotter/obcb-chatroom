import obcb_comms
import threading
import json
import argparse
import hashlib

parser = argparse.ArgumentParser()
parser.add_argument("room", help="page* to communicate on")
parser.add_argument("user", help="username to use")
args = parser.parse_args()

sock = obcb_comms.socket(int(args.room))
previousMsg = None
die = False
inBuf = ""

# input fucking sucks, we're using getch
class _Getch:
    """Gets a single character from standard input.  Does not echo to the screen."""
    def __init__(self):
        try:
            self.impl = _GetchWindows()
        except ImportError:
            self.impl = _GetchUnix()

    def __call__(self): return self.impl()

class _GetchUnix:
    def __init__(self):
        import tty, sys

    def __call__(self):
        import sys, tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch.encode('utf-8')

class _GetchWindows:
    def __init__(self):
        import msvcrt

    def __call__(self):
        import msvcrt
        return msvcrt.getch()

def md5(text):
    return hashlib.md5(text.encode()).hexdigest()

def rx():
    global previousMsg
    while True:
        try:
            a = sock.recvall()
            if die: break

            #no reason to use json, just felt like it
            try:
                t = json.loads(a)

                # verify that the fields we need exist

                assert t.get("user", False) != False
                assert t.get("text", False) != False
                assert t.get("crc", False) != False

                assert md5(t["text"]) == t["crc"] # verify that the checksum matches the text
            except:
                continue
            
            # make sure that we haven't printed the same message before
            if hash(t["text"]) == previousMsg:
                continue

            previousMsg = hash(t["text"])
            print("\r\033[K", end="", flush=True)
            print("\r{}: {}\033[0m\n> ".format(t["user"], t["text"]), end="", flush=True)
            print(inBuf, end="", flush=True)
        except: # wrap the whole thing into a try catch statement to prevent random bricking (stupid but works)
            pass

getch = _Getch()
def tx():
    global inBuf
    while True:

        inBuf = ""
        while True:
            char = getch()

            if char == b"\r":
                break
            elif char == b'\x03':
                raise KeyboardInterrupt()
            elif char in [b'\b', b'\x08', b'\x7f']:
                inBuf = inBuf[:-1]
                print("\r\033[K", end="", flush=True)
                print("\r> "+inBuf, end="", flush=True)
            else:
                inBuf += char.decode('utf-8')
                print("\r> "+inBuf, end="", flush=True)

        msg = "\033[0m" + "\033[1;40;32m" + inBuf + "\033[0m"

        sock.sendall(json.dumps({"user": args.user, "text": msg, "crc": md5(msg)}))

a = threading.Thread(target=rx)
a.start()

try:
    sock.sendall(json.dumps({"user": args.user, "text": "joined the chat", "crc": md5("joined the chat")}))
    tx()
except:
    die = True
    raise