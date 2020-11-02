import socket
import argparse
import re
import time
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
    ack = removeprefix(header[1], "Acknowledgment: ")
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
            return ("{}\r\nAcknowledgment: {}\r\nWindow: {}\r\n\r\n{}".format(self.command, self.ack, self.window, self.data))

def outputLog(sendRecv, packet):
    now = datetime.now()
    date = datetime.strftime(now, '%a %b %d %H:%M:%S PDT %Y')
    if packet.command != "ACK":
        print("{}: {}; {}; Sequence: {}; Length: {}".format(date, sendRecv, packet.command, packet.seq, packet.length))
    else: #ACK packet
        print("{}: {}; {}; Acknowledgment: {}; Window: {}".format(date, sendRecv, packet.command, packet.ack, packet.window))
    return
    

parser = argparse.ArgumentParser()
parser.add_argument("ip_address")
parser.add_argument("port_number", type=int)
parser.add_argument("read_file_name")
parser.add_argument("write_file_name")
args = parser.parse_args()

rdpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

rdpSocket.bind(("h1", args.port_number))
rdpSocket.settimeout(0.5)

fIn = open(args.read_file_name, "r")
fOut = open(args.write_file_name, "w")
f = fIn.read()
fIn.close()
filesize = len(f)
totalPackets = int(filesize/1024) + 1
#print("inString size: {}, Total packets to write: {}".format(len(f),totalPackets))


writeString = ""
writtenPackets = 0
MAX_WINDOW = 1024*5
recvWindow = MAX_WINDOW
acknum = 0
inAck = 1
prevAck = -1
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
            acknum += 1
            outPacket = packet("ACK",-1,acknum,0)
            rdpSocket.sendto(outPacket.packString().encode(), ("h2", args.port_number))
            outputLog("Send",outPacket)
        else: #command is ACK
            seqnum += 1
            break
    except socket.timeout: #Packet Dropped, reset and send packets again
        seqnum = 0
        acknum = 0
        #print("Timed out, resending...")
        outPacket = packet("SYN",seqnum,-1,-1,0)
        rdpSocket.sendto(outPacket.packString().encode(), ("h2", args.port_number))
        outputLog("Send",outPacket)
        
while True:
    if writtenPackets == totalPackets: #all packets sent
        break
    if noLoss:  # toDo (detect loss) (Sends new packets if no loss detected)
        if recvWindow > 0:  # window still has room
       
            outPacket = packet("DAT")  # create packet
           
            if (filesize - seqnum <= 1024):  # Remaining file size is less than a full packet
                outPacket.length = filesize - seqnum + 1
                recvWindow = 0
            elif recvWindow > 1024:  # send full packet
                outPacket.length = 1024
            else:  # send partial packet
                outPacket.length = recvWindow
                
           
            outPacket.seq = seqnum
            recvWindow -= outPacket.length
            outPacket.data = f[seqnum - 1:seqnum + outPacket.length - 1]
            rdpSocket.sendto(outPacket.packString().encode(), ("h2", args.port_number))
            seqnum += outPacket.length
            outputLog("Send",outPacket)
        else: #recieve packets now that window is full
            recvWindow = MAX_WINDOW
            dupes = 0
            while True:
                try:
                    data = rdpSocket.recvfrom(3072)
                    data = data[0].decode()
                    inPacket = packPacket(data) #convert data into packet object
                    outputLog("Receive",inPacket)

                    if inPacket.command == "DAT":
                        #recieve DAT packet with sequence number and length 
                        inSeq = inPacket.seq
                        #print("inSeq: {}, inAck: {}".format(inSeq,inAck))
                        if inSeq == inAck: #packet in correct sequence
                            inAck = inSeq + inPacket.length
                            outPacket = packet("ACK",-1,inAck,recvWindow)
                            rdpSocket.sendto(outPacket.packString().encode(), ("h2", args.port_number))
                            outputLog("Send", outPacket)
                            fOut.seek(inSeq - 1)
                            fOut.write(inPacket.data)
                            writtenPackets += 1
                            #print("Written {}/{} packets to file, from position {}-{}. SEQ: {}, ACK:{}".format(writtenPackets,totalPackets,(inSeq-1),(inAck-1),seqnum,acknum)) 
                        elif inSeq >= inAck: #packet out of order
                            #print("Packet out of order...")
                            outPacket = packet("ACK",-1,inAck,recvWindow)
                            rdpSocket.sendto(outPacket.packString().encode(), ("h2", args.port_number))
                            outputLog("Send", outPacket)
                            noLoss = False
                        else: #packet repeat
                            #print("Duplicate packet")
                            pass
                    else: #command = ACK
                        if prevAck == inPacket.ack:
                            dupes += 1
                            if dupes > 2:
                                dupes = 0
                                #print("Fast Retransmit...")
                                break
                        prevAck = inPacket.ack
                        acknum = inPacket.ack #acknum = last confirmed inAck
                        #print("acknum updated to {}".format(acknum))
                        if seqnum == inPacket.ack: #Data received
                            #print("Successful Pass...")
                            break
                    time.sleep(0.1)
                except socket.timeout:
                    #print("Socket Timeout...")
                    break
    else:  # loss detected. Resend packet(s)
        seqnum = acknum #send from last confirmed successful packet
        #print("Loss detected, resending from byte {}".format(seqnum))        
        noLoss = True       
    time.sleep(0.1)
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
            
            outPacket = packet("ACK",-1,(seqnum + inPacket.length),0)
            rdpSocket.sendto(outPacket.packString().encode(), ("h2", args.port_number))
            outputLog("Send",outPacket)
        else: #command is ACK
            fOut.close
            rdpSocket.close()
            break
    except socket.timeout: #Packet Dropped, reset and send packets again
        #print("Timed out, resending...")
        outPacket = packet("FIN",seqnum,-1,-1,0)
        rdpSocket.sendto(outPacket.packString().encode(), ("h2", args.port_number))
        outputLog("Send",outPacket)




