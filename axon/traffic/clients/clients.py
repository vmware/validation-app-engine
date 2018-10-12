import abc
import datetime
import itertools
import six
import socket
from threading import Thread
import time

from axon.common.consts import PACKET_SIZE
from axon.traffic.resources import TCPRecord, UDPRecord
from axon.traffic.recorder import SqliteDbRecorder


@six.add_metaclass(abc.ABCMeta)
class Client(object):

    @abc.abstractmethod
    def ping(self):
        """
        Send the traffic to a endpoint
        :return:  None
        """
        pass

    @abc.abstractmethod
    def record(self):
        """
        Record the data to a data source
        :return: None
        """
        pass


class TCPClient(Client):
    def __init__(self, source, destination, port, connected=True,
                 recorder=None, request_count=1):
        """
        Client to send TCP requests
        :param source: source ip
        :type source: string
        :param destination: destination ip
        :type destination: str
        :param port: destination server port
        :type port: int
        :param recorder: recorder object which will record the data
        :type recorder: TrafficRecorder
        """
        self._source = source
        self._port = port
        self._destination = destination
        self._start_time = None
        self._recorder = recorder()
        self._request_count = request_count
        self._connected = connected

    def _create_socket(self, address_family=socket.AF_INET,
                       socket_type=socket.SOCK_STREAM):
        """
        Creates a socket
        :param address_family: address family
        :type address_family: socket address family object
        :param socket_type: type of the socket i.e. STREAM or DATAGRAM
        :type socket_type: socket type object
        :return: created socket
        :rtype: socket object
        """
        sock = socket.socket(address_family, socket_type)
        sock.settimeout(2)
        return sock

    def __connect(self, sock):
        """
        Create a connection to the server
        :param sock: socket object
        :type sock: socket
        """
        sock.connect((self._destination, self._port))

    def _send_receive(self, sock, payload):
        """
        Send and recieve the packet
        :param sock: socket which is connected to server
        :type sock: socket
        :param payload: data to be send
        :type payload: str
        :return: data returned from server
        :rtype: str
        """
        try:
            sock.send(payload)
            sock.recv(PACKET_SIZE)
        except Exception as e:
            # TODO(pksingh) add logging
            print(e, 'TCP')
            raise
        finally:
            sock.close()

    def _get_latency(self):
        """
        Get latency of the request
        :return: latency of the request
        :rtype: float
        """
        time_diff = datetime.datetime.now() - self._start_time
        return time_diff.seconds * 1000 + time_diff.microseconds * .001

    def record(self, success=True, error=None):
        """
        Record the traffic to data source
        :return: None
        """
        success = bool(self._connected) == bool(success)
        if self._recorder:
            record = TCPRecord(
                self._source, self._destination, self._port,
                self._get_latency(),
                error, success)
            self._recorder.record_traffic(record)

    def ping(self):
        # TODO(pksingh) Decide on payload
        payload = 'Dinkirk'.encode()
        for _ in range(self._request_count):
            try:
                self._start_time = datetime.datetime.now()
                sock = self._create_socket()
                self.__connect(sock)
                self._send_receive(sock, payload)
                self.record()
            except Exception as e:
                self.record(success=False, error=str(e))


class UDPClient(TCPClient):

    def ping(self):
        # TODO(pksingh) Decide on payload
        payload = 'Dinkirk'.encode()
        for _ in range(self._request_count):
            try:
                self._start_time = datetime.datetime.now()
                sock = self._create_socket(socket.AF_INET, socket.SOCK_DGRAM)
                self._send_receive(sock, payload)
                self.record()
            except Exception as e:
                self.record(success=False, error=str(e))

    def _send_receive(self, sock, payload):
        """
        Send and receive the packet
        :param sock: socket which is connected to server
        :type sock: socket
        :param payload: data to be send
        :type payload: str
        :return: data returned from server
        :rtype: str
        """
        try:
            sock.sendto(payload, (self._destination, self._port))
            sock.recvfrom(PACKET_SIZE)
        except Exception as e:
            # TODO(pksingh) add logging
            print(e, 'UDP')
            raise
        finally:
            sock.close()

    def record(self, success=True, error=None):
        """
        Record the traffic to data source
        :return: None
        """
        success = bool(self._connected) == bool(success)
        if self._recorder:
            record = UDPRecord(
                self._source, self._destination, self._port,
                self._get_latency(), error, success)
            self._recorder.record_traffic(record)


class TrafficClient(object):

    REQUEST_RATE = 100

    def __init__(self, src, destinations, request_rate=100):
        self._src = src
        self._reqest_rate = min(request_rate, len(destinations))
        self._destinations = itertools.cycle(destinations)

    def _send_traffic(self):
        threads = []
        for _ in range(self.REQUEST_RATE):
            protocol, port, endpoint, connected = next(self._destinations)
            if protocol == "TCP":
                client = TCPClient(
                    self._src, endpoint, port,
                    connected, SqliteDbRecorder)
            if protocol == "UDP":
                client = UDPClient(
                    self._src, endpoint, port,
                    connected, SqliteDbRecorder)
            thread = Thread(target=client.ping)
            thread.daemon = True
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()

    def run(self):
        while True:
            self._send_traffic()
            time.sleep(20)
