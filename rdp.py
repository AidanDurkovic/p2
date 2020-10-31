import socket
import argparse
import re
from datetime import datetime


def removeprefix(text, prefix):
    if text.startswith(prefix):
        return text[len(prefix):]
    return -1


# python can't do multiple constructors for some reason so this has to be a seperate method
def packPacket(packString):
    partString = packString.partition("\r\n\r\n")
    data = partString[2]
    header = partString[0].split("\r\n", 2)
    command = header[0]  # line one is always the command

    # line 2 is either Seq for DAT packets or Ack for ACK packets
    seq = removeprefix(header[1], "Sequence: ")
    ack = removeprefix(header[1], "Acknowledgement: ")
    # line 3 is either length for DAT packets or window for ACK packets
    length = removeprefix(header[2], "Length: ")
    window = removeprefix(header[2], "Window: ")
    seq = int(seq)
    ack = int(ack)
    length = int(length)
    window = int(window)
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
            return ("{}\r\nSequence: {}\r\nLength: {}\r\n\r\n{}".format(self.command, self.seq, self.length, self.data))
        else:  # ACK packet
            return ("{}\r\nAcknowledgement: {}\r\nWindow: {}\r\n\r\n{}".format(self.command, self.ack, self.window, self.data))

def outputLog(sendRecv, packet):
    now = datetime.now()
    date = datetime.strftime(now, '%a %b %d %H:%M:%S PDT %Y')
    if packet.command != "ACK":
        print("{}: {}; {}; {}; {};".format(date, sendRecv, packet.command, packet.seq, packet.length))
    else: #ACK packet
        print("{}: {}; {}; {}; {};".format(date, sendRecv, packet.command, packet.ack, packet.window))
    return
    

parser = argparse.ArgumentParser()
parser.add_argument("ip_address")
parser.add_argument("port_number", type=int)
parser.add_argument("read_file_name")
parser.add_argument("write_file_name")
args = parser.parse_args()

print(args.ip_address)

rdpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

rdpSocket.bind((args.ip_address, args.port_number))
rdpSocket.settimeout(1)

readFile = open(args.read_file_name, "r")
f = readFile.read()
totalPackets = int(len(f)/1024) + 1
print("inString size: {}, Total packets to write: {}".format(len(f),totalPackets))
readFile.close()
writeString = ""
writtenPackets = 0
recvWindow = 1024*4
acknum = 0
seqnum = 0
noLoss = True

#Send SYN
outPacket = packet("SYN",seqnum,-1,-1,0)
rdpSocket.sendto(outPacket.packString().encode(), ("h2", args.port_number))
outputLog("Send",outPacket)

while True:
    try:
        data = rdpSocket.recvfrom(2048)
        data = data[0].decode()
        inPacket = packPacket(data) #convert data into packet object
        outputLog("Receive",inPacket)

        if inPacket.command == "SYN":
            acknum = acknum + inPacket.length + 1 
            outPacket = packet("ACK",-1,acknum,0)
            rdpSocket.sendto(outPacket.packString().encode(), ("h2", args.port_number))
            outputLog("Send",outPacket)
        else: #command is ACK
            seqnum = seqnum + inPacket.window + 1
            break
    except socket.timeout: #Packet Dropped, reset and send packets again
        print("Timed out, resending...")
        acknum = 0
        seqnum = 0
        outPacket = packet("SYN",seqnum,-1,-1,0)
        rdpSocket.sendto(outPacket.packString().encode(), ("h2", args.port_number))
        outputLog("Send",outPacket)
        
while True:
    if writtenPackets == totalPackets: #all packets sent
        break 
    if recvWindow > 0:  # window still has room
        if noLoss:  # toDo (detect loss) (Sends new packets if no loss detected)
            outPacket = packet("DAT")  # create packet
           
            if (len(f) - seqnum <= 1024):  # Remaining file size is less than a full packet
                outPacket.length = len(f) - seqnum
                recvWindow = 0
            elif recvWindow > 1024:  # send full packet
                outPacket.length = 1024
            else:  # send partial packet
                outPacket.length = recvWindow
                
           
            outPacket.seq = seqnum
            recvWindow -= outPacket.length
            outPacket.data = f[seqnum:outPacket.length]
            rdpSocket.sendto(outPacket.packString().encode(), ("h2", args.port_number))
            seqnum += outPacket.length
            outputLog("Send",outPacket)

        else:  # loss detected. Resend packet(s)
            print("Loss detected, resending...")
            data = rdpSocket.recvfrom(3072) #get last ack packet
            data = data[0].decode()
            inPacket = packPacket(data)
            seqnum = inPacket.ack #send from last confirmed successful packet
            noLoss = True       
    else: #recieve packets now that window is full 
        while True:
            try:
                data = rdpSocket.recvfrom(3072)
                data = data[0].decode()
                inPacket = packPacket(data) #convert data into packet object
                outputLog("Receive",inPacket)
                
                if inPacket.command == "DAT":
                    #recieve DAT packet with sequence number and length 
                    inSeq = inPacket.seq
                    if inSeq == acknum: #packet in correct sequence
                        acknum = inSeq + inPacket.length
                        recvWindow = recvWindow + inPacket.length
                        outPacket = packet("ACK",-1,acknum,recvWindow)
                        rdpSocket.sendto(outPacket.packString().encode(), ("h2", args.port_number))
                        outputLog("Send", outPacket)
                        writeString += inPacket.data
                        writtenPackets += 1
                        print("Written {}/{} packets to file, SEQ: {}, ACK:{}".format(writtenPackets,totalPackets,seqnum,acknum)) 
                    else: #packet is out of order
                        print("Packet out of order...")
                        noLoss = False
                        break
                else: #command = ACK
                    if seqnum == inPacket.ack: #Data received
                        break
            except socket.timeout:
                print("Socket Timeout...")
                noLoss = False
                break

#Send FIN
outPacket = packet("FIN",seqnum,-1,-1,0)
rdpSocket.sendto(outPacket.packString().encode(), ("h2", args.port_number))
outputLog("Send",outPacket)

while True:
    try:
        data = rdpSocket.recvfrom(2048)
        data = data[0].decode()
        inPacket = packPacket(data) #convert data into packet object
        outputLog("Receive",inPacket)

        if inPacket.command == "FIN":
            acknum = acknum + inPacket.length + 1 
            outPacket = packet("ACK",-1,acknum,0)
            rdpSocket.sendto(outPacket.packString().encode(), ("h2", args.port_number))
            outputLog("Send",outPacket)
        else: #command is ACK
            fOut = open(args.write_file_name, "w")
            fOut.write(writeString)
            fOut.close
            rdpSocket.close()
            break
    except socket.timeout: #Packet Dropped, reset and send packets again
        print("Timed out, resending...")
        acknum = 0
        seqnum = 0
        outPacket = packet("FIN",seqnum,-1,-1,0)
        rdpSocket.sendto(outPacket.packString().encode(), ("h2", args.port_number))
        outputLog("Send",outPacket)




