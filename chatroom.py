import os, obcb_comms, threading, json, argparse, hashlib

parser = argparse.ArgumentParser()
parser.add_argument("room", help="page* to communicate on")
parser.add_argument("user", help="username to use")
parser.add_argument("-p", "--prepend", help="text to prepend to message (supports ANSI!)", default="")
args = parser.parse_args()

sock = obcb_comms.socket(int(args.room))
termHeight = os.get_terminal_size().lines - 2
msgBuffer = ["" for _ in range(termHeight)]
die = False

def md5(text):
    return hashlib.md5(text.encode()).hexdigest()

def escapeLiteral(literal):
    return literal.replace("\\\\", "\\").encode("utf-8").decode("unicode_escape")

def rx():
    global die
    while True:
        try:
            if die: return

            a = sock.recvall(timeout=0.1)

            if a == None: continue

            try:
                t = json.loads(a) #no reason to use json, just felt like it

                # verify that the fields we need exist
                assert t.get("user", False) != False
                assert t.get("text", False) != False
                assert t.get("crc", False) != False

                assert md5(t["text"]) == t["crc"] # verify that the checksum matches the text
            except:
                continue

            msgBuffer.pop(0)
            msgBuffer.append("{}: {}".format(t["user"], t["text"]))

            #   save cursor  move to 0,0       print new messages   restore cursor pos
            print("\033[s" + "\033[1;1f" + "\n\033[K".join(msgBuffer) + "\033[u", end="", flush=1) # move to first line, first col
        except: # wrap the whole thing into a try catch statement to prevent random bricking (stupid but works)
            pass

def tx():
    while True:
        msg = "\033[0m" + escapeLiteral(args.prepend) + input(">") + "\033[0m"

        #      1 ln up      clear ln    CR
        print("\033[1A\r" + "\033[K" + "\r", end="", flush=1)

        sock.sendall(json.dumps({"user": args.user, "text": msg, "crc": md5(msg)}))

#    clear term  print line placeholders
print("\033[2J" + "\n".join(msgBuffer), end="", flush=True) 

try:
    threading.Thread(target=rx).start()
    sock.sendall(json.dumps({"user": args.user, "text": "joined the chat", "crc": md5("joined the chat")}))
    tx()
except:
    die = True
    print("quitting")
    quit()