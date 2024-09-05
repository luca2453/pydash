from r2a.ir2a import *
from player.parser import *
from player.player import *
import time
from base.timer import Timer

class R2ANewAlgoritm4(IR2A):
    def __init__(self, id):
        IR2A.__init__(self, id)

        self.whiteboard = Whiteboard.get_instance() # Whiteboard object to change statistical information between Player and R2A algorithm
        
        self.parsed_mpd = '' #Arquivo xml
        
        self.qi = [] # Vetor com as qualidades
                
        self.request_time = 0 # Tempo inicial da requisição
        
        self.throughput = [] # Vetor dos touroughputs
        
        self.qualidadeAtual = 15 # Qualidade inicial
        
        self.historicoQualidades = [] # Historico de qualidades
        
        self.segment_size_response = 0 # Tamanho do seguimento inicial
        
        self.p = 1 # Inicialização da probabilidade de mudança da qualidade

        self.listP = [1] # Vetor com o historico das probabilidades(self.p) de mudanças
        
        self.inicial = 1 # Primeira solicitação
        

    def handle_xml_request(self, msg):
        self.send_down(msg)
        pass


    def handle_xml_response(self, msg):
        # Aqui ele vai receber a primeira resposta, com ela, foi pego o arquivo XML
        self.parsed_mpd = parse_mpd(msg.get_payload())
        
        # Aqui ele vai pegar todas as qualidades do arquvio XML e guardar em um vetor
        self.qi = self.parsed_mpd.get_qi()
                
        # Apos isso ele manda para a camada de cima a resposta
        self.send_up(msg)
        pass


    def handle_segment_size_request(self, msg):
        '''Após a camada superior receber a primeira resposta, ela solicita os segmentos, e o pedido cai aqui.'''
        
        # Verifica se é a primeira solicitação de segmento
        if self.inicial:
            self.inicial -= 1  # Marca que a solicitação inicial já foi feita
        else:
            # Calcula a média das últimas probabilidades (até 5) para tomar decisões mais estáveis
            avg_prob = sum(self.listP[-5:]) / min(len(self.listP), 5)
            
            # Debbung: Verificar historico de probabilidade, media e probabilidade
            # print(f'Historico de probabilidades: {self.listP}')
            # print(f'Media da probabilidade: {avg_prob}, Probabilidade: {self.p}')
            
            # Avalia o tamanho do buffer de vídeo disponível
            if self.whiteboard.get_amount_video_to_play() < 10:  # Se o buffer for pequeno
                # Se a média das probabilidades for maior que a atual, diminui a qualidade
                if avg_prob > self.p:
                    # Diminui a qualidade se ainda não estiver na qualidade mínima
                    if self.qualidadeAtual > 0:
                        self.qualidadeAtual -= 1
            # Se o buffer for maior que 20, avalia para aumentar a qualidade
            elif self.whiteboard.get_amount_video_to_play() > 15:
                # Se a média for menor que a probabilidade atual, aumenta a qualidade
                if avg_prob < self.p:
                    # Aumenta a qualidade se ainda não estiver na máxima
                    if self.qualidadeAtual < 19:
                        self.qualidadeAtual += 1
        
        # Marca o tempo do início da solicitação do segmento
        self.request_time = time.perf_counter()
        
        # Guarda a probabilidade atual no histórico de probabilidades
        self.listP.append(self.p)
        
        # Guarda a qualidade atual no histórico de qualidades
        self.historicoQualidades.append(self.qualidadeAtual)
        
        # Debbung: Verificar historico de qualidade
        # print(f'Historico de qualidade: {self.historicoQualidades}')
        
        # Define a qualidade do segmento solicitado
        msg.add_quality_id(self.qi[self.qualidadeAtual])
        
        # Envia a solicitação para a camada inferior
        self.send_down(msg)

    def handle_segment_size_response(self, msg):
        '''Recebe a resposta do segmento da camada inferior e calcula o throughput para a próxima solicitação.'''

        # Verifica se a mensagem de resposta do segmento foi encontrada
        if msg.found():
            # Calcula o tempo decorrido desde a solicitação
            elapsed_time = time.perf_counter() - self.request_time

            # Evita divisão por zero verificando se o tempo transcorrido é maior que zero
            if elapsed_time > 0:
                # Calcula o throughput medido (tamanho do segmento em bits dividido pelo tempo decorrido)
                measured_throughput = msg.get_bit_length() / elapsed_time

                # Limita o histórico de throughput a no máximo 50 medições
                if len(self.throughput) >= 50:
                    del self.throughput[0]  # Remove o throughput mais antigo
                self.throughput.append(measured_throughput)

        # Calcula a média simples dos throughputs
        mediaThroughput = 0
        items = self.throughput

        # Se houver dados de throughput, calcula a média
        if items:
            mediaThroughput = sum(items) / len(items)

        # Calcula a média ponderada dos throughputs, dando mais peso aos valores mais recentes
        mediaThroughput_pesos = 0
        for i in range(1, len(items) + 1):
            # Aplica pesos crescentes aos throughputs mais recentes
            mediaThroughput_pesos += abs(items[i - 1] - mediaThroughput) * (i / len(items))
        
        # Divide pela quantidade de elementos para obter a média ponderada
        mediaThroughput_pesos = mediaThroughput_pesos / len(items)

        # Calcula a nova probabilidade com base na média dos throughputs e na média ponderada
        if (mediaThroughput + mediaThroughput_pesos) > 0:
            self.p = mediaThroughput / (mediaThroughput + mediaThroughput_pesos)

        # Debbung: Exibe informações sobre a qualidade e probabilidade atual
        # print(f'Qualidade atual: {self.qualidadeAtual}')
        # print(f'Probabilidade: {self.p}')
        # print(f'Media de T: {mediaThroughput}')
        # print(f'Media de T com pesos: {mediaThroughput_pesos}')
        
        # Envia a resposta para a camada superior
        self.send_up(msg)
        
    def initialize(self):
        SimpleModule.initialize(self)
        pass

    def finalization(self):
        SimpleModule.finalization(self)
        pass