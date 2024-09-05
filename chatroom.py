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
            print("\r{}: {}\n>".format(t["user"], t["text"]), end="", flush=True)
        except: # wrap the whole thing into a try catch statement to prevent random bricking (stupid but works)
            pass

def tx():
    while True:
        msg = input("\033[0m\n>") # + reset ansi to prevent annoying ansi codes

        sock.sendall(json.dumps({"user": args.user, "text": msg, "crc": md5(msg)}))

a = threading.Thread(target=rx)
a.start()

try:
    sock.sendall(json.dumps({"user": args.user, "text": "joined the chat", "crc": hash("joined the chat")}))
    tx()
except KeyboardInterrupt:
    print("^C")
    die = True