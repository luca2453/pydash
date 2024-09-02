from r2a.ir2a import *
from player.parser import *
from player.player import *
import time
from base.timer import Timer

class R2ANewAlgoritm3(IR2A):

    def __init__(self, id):
        IR2A.__init__(self, id)

        self.whiteboard = Whiteboard.get_instance()
        self.parsed_mpd = ''
        self.qi = []
        self.request_time = 0
        self.throughput = []
        self.qualidadeAtual = 10
        self.historicoQualidades = []
        self.segment_size_response = 0
        self.p = 1
        self.listP = [1]
        self.inicial = 1
        self.ewma_throughput = None
        self.alpha = 0.3  # Fator de suavização para EWMA

    def handle_xml_request(self, msg):
        self.request_time = time.perf_counter()
        self.send_down(msg)
        pass

    def handle_xml_response(self, msg):
        self.parsed_mpd = parse_mpd(msg.get_payload())
        self.qi = self.parsed_mpd.get_qi()
        self.segment_size_response_time = time.time()
        self.send_up(msg)
        pass

    def handle_segment_size_request(self, msg):
        buffer_size = self.whiteboard.get_amount_video_to_play()

        if self.inicial:
            self.inicial -= 1
        else:
            if buffer_size < 10:
                if self.qualidadeAtual > 0:
                    self.qualidadeAtual -= 1

            elif buffer_size > 15 and self.ewma_throughput > self.qi[self.qualidadeAtual + 1] and self.qualidadeAtual < 19:
                self.qualidadeAtual += 1

        self.request_time = time.perf_counter()
        self.historicoQualidades.append(self.qualidadeAtual)
        msg.add_quality_id(self.qi[self.qualidadeAtual])
        self.send_down(msg)

    def handle_segment_size_response(self, msg):
        self.segment_size_response = msg.get_bit_length()

        if msg.found():
            elapsed_time = time.perf_counter() - self.request_time

            if elapsed_time > 0:
                measured_throughput = msg.get_bit_length() / elapsed_time

                if self.ewma_throughput is None:
                    self.ewma_throughput = measured_throughput
                else:
                    self.ewma_throughput = (self.alpha * measured_throughput) + ((1 - self.alpha) * self.ewma_throughput)

                if len(self.throughput) < 50:
                    self.throughput.append(measured_throughput)
                else:
                    del self.throughput[0]
                    self.throughput.append(measured_throughput)

        self.send_up(msg)

    def initialize(self):
        SimpleModule.initialize(self)
        pass

    def finalization(self):
        SimpleModule.finalization(self)
        pass
