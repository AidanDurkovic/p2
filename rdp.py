import time
import socket
import argparse

def removeprefix(text, prefix):
    if text.startswith(prefix):
        return text[len(prefix):]
    return text

def packPacket(packString):
        packString = "Hello"
        partString = packString.partition("\n\n")
        data = partString[2]
        header = partString[0].split("\n")
        command = header[0]
        seq = removeprefix(header[1], "Sequence: ")
        ack = removeprefix(header[2], "Acknowledgement: ")
        window = removeprefix(header[3], "Window: ")
        length = removeprefix(header[4], "Length")
        return packet(command,seq,ack,window,length,data)

class packet:
    def __init__(self,command,seq = 0,ack = 0,window = 0,length = 0,data =""):
        self.command = command
        self.seq = seq
        self.ack = ack
        self.window = window
        self.length = length
        self.data = data
    def toString(self):
        return ("{}\nSequence: {}\nAcknowledgement: {}\nWindow: {}\nLength: {}\n\n{}".format(self.command, self.seq, self.ack, self.window, self.length, self.data))



parser = argparse.ArgumentParser()
parser.add_argument("ip_address")
parser.add_argument("port_number", type=int)
parser.add_argument("read_file_name")
parser.add_argument("write_file_name")
args = parser.parse_args()

rdp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
rdp_socket.bind(args.ip_address, args.port_number)
rdp_socket.settimeout(2)

readFile = open(args.read_file_name, "r")
recvWindow = "2048"
seqnum = 0
while True:
    if 0: #toDo (all packets sent)
        break
    if recvWindow > 0: #window still has room
        if noLoss: #toDo (detect loss) (Sends new packets if no loss detected)
            packToSend = packet("DAT") #create packet
            if recvWindow > 1024: #send full packet
                packToSend.length = 1024
            else: #send partial packet
                packToSend.length = recvWindow
            recvWindow -= packToSend.length
            #Packet is packed with DAT, Seq, and Lenght. Ack and Window are not needed for DAT packets
            
        
    