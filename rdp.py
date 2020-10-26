import time
import socket
import argparse
import datetime


def removeprefix(text, prefix):
    if text.startswith(prefix):
        return text[len(prefix):]
    return -1


# python can't do multiple constructors for some reason so this has to be a seperate method
def packPacket(packString):
    partString = packString.partition("\n\n")
    data = partString[2]
    header = partString[0].split("\n", 2)
    command = header[0]  # line one is always the command
    # line 2 is either Seq for DAT packets or Ack for ACK packets
    seq = removeprefix(header[1], "Sequence: ")
    ack = removeprefix(header[1], "Acknowledgement: ")
    # line 3 is either length for DAT packets or window for ACK packets
    length = removeprefix(header[2], "Length: ")
    window = removeprefix(header[2], "Window: ")
    return packet(command, seq, ack, window, length, data)


class packet:
    def __init__(self, command, seq=-1, ack=-1, window=-1, length=-1, data=""):
        self.command = command
        self.seq = seq
        self.ack = ack
        self.window = window
        self.length = length
        self.data = data

    def packString(self):
        if self.command != "ACK":  # DAT, FIN, or SYN
            return ("{}\nSequence: {}\nLength: {}\n\n{}".format(self.command, self.seq, self.length, self.data))
        else:  # ACK packet
            return ("{}\nAcknowledgement: {}\nWindow: {}\n\n{}".format(self.command, self.ack, self.window, self.data))

def outputLog(sendRecv, packet):
    date = datetime.now()
    date = datetime.strftime(date, '%a %b %d %H:%M:%S PDT %Y')
    if packet.command != "ACK":
        print("{Date}: {sendRecv}; {Command}; {SeqAck}; {LenWin};".format(date, sendRecv, packet.command, packet.seq, packet.length))
    else: #ACK packet
        print("{Date}: {sendRecv}; {Command}; {SeqAck}; {LenWin};".format(date, sendRecv, packet.command, packet.ack, packet.window))
    return
    

parser = argparse.ArgumentParser()
parser.add_argument("ip_address")
parser.add_argument("port_number", type=int)
parser.add_argument("read_file_name")
parser.add_argument("write_file_name")
args = parser.parse_args()

rdpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
rdpSocket.bind(args.ip_address, args.port_number)
rdpSocket.settimeout(2)

readFile = open(args.read_file_name, "r")
f = readFile.read()

recvWindow = "2048"
acknum = 0
seqnum = 0
packetsSent = 0
#Send SYN
outPacket = packet("SYN",seqnum,-1,-1,0)
rdpSocket.sendto(outPacket.packString().encode(), ("h2", 8888))
outputLog("Send",outPacket)

while True:
    data, addr = rdpSocket.recvfrom(256)
    inPacket = packPacket(data) #convert data into packet object
    outputLog("Receive",inPacket)
    try:
        if inPacket.command == "SYN":
            acknum = acknum + inPacket.length + 1 
            outPacket = packet("ACK",-1,acknum,recvWindow)
            rdpSocket.sendto(outPacket.packString().encode(), ("h2", 8888))
            outputLog("Send",outPacket)
        else: #command is ACK
            seqnum = seqnum + inPacket.length + 1
            break
    except socket.timeout: #Packet Dropped, reset and send packets again
        print("Timed out, resending...")
        acknum = 0
        seqnum = 0
        outPacket = packet("SYN",seqnum,-1,-1,0)
        rdpSocket.sendto(outPacket.packString().encode(), ("h2", 8888))
        outputLog("Send",outPacket)




while True:
    if 0:  # toDo (all packets sent)
        break
    if recvWindow > 0:  # window still has room
        if noLoss:  # toDo (detect loss) (Sends new packets if no loss detected)
            outPacket = packet("DAT")  # create packet
           
            if (len(f) - readFile.tell()) <= 1024:  # Remaining file size is less than a full packet
                outPacket.length = len(f) - readFile.tell()
            elif recvWindow > 1024:  # send full packet
                outPacket.length = 1024
            else:  # send partial packet
                outPacket.length = recvWindow
           
            outPacket.seq = seqnum
            recvWindow -= outPacket.length
            outPacket.data = f[seqnum:outPacket.length]
            outPacket.data = outPacket.data + "\n"
            packetsSent += 1
            seqnum += outPacket.length
            rdpSocket.sendto(outPacket.packString().encode(), ("h2", 8888))

        else:  # loss detected. Resend previous window of packets
            print()
    else: #send packets now that window is full | 
        while True:
            try:
                data, addr = rdpSocket.recvfrom(3072) #recv with room for header too
                data = data[0:-1]
                inPacket = packPacket(data) #convert data into packet object

                if inPacket.command == "DAT":
                    #recieve DAT packet with sequence number and length 
                    #send ack packets until seq# = ack#
                    print()
            except socket.timeout:
                noLoss = False
                break
            




