from r2a.ir2a import *
import requests
from player.parser import *
from player.player import *
import time
from base.timer import Timer

class R2ANewAlgoritm1(IR2A):

    def __init__(self, id):
        IR2A.__init__(self, id)

        # Whiteboard object to change statistical information between Player and R2A algorithm
        self.whiteboard = Whiteboard.get_instance()
        
        #Arquivo xml
        self.parsed_mpd = ''
        
        # Vetor com as qualidades
        self.qi = []
        
        # Tempo inicial da requisição
        self.request_time = 0

        # Vetor dos touroughputs
        self.throughput = []

        # Qualidade inicial
        self.qualidadeAtual = 10
        
        # Historico de qualidades
        self.historicoQualidades = []
        
        # Tamanho do seguimento inicial
        self.segment_size_response = 0
        
        # Inicialização da probabilidade de mudança da qualidade
        self.p = 1

        # Vetor com o historico das probabilidades(self.p) de mudanças
        self.listP = [1]
        
        # Primeira solicitação
        self.inicial = 1
        

    def handle_xml_request(self, msg):
        # Primeira requisição, ele vai marcar o tempo inicial da requisição, e depois vai descer pra camada de baixo
        # para solicitar o arquivo XML
        self.request_time = time.perf_counter()
        self.send_down(msg)
        pass


    def handle_xml_response(self, msg):
        # Aqui ele vai receber a primeira resposta, com ela, foi pego o arquivo XML
        self.parsed_mpd = parse_mpd(msg.get_payload())
        
        # Aqui ele vai pegar todas as qualidades do arquvio XML e guardar em um vetor
        self.qi = self.parsed_mpd.get_qi()
        
        # Depois ele vai pegar o tempo da resposta, para com isso podermos calcular o touroughputs dessa requisição
        self.segment_size_response_time = time.time()
        
        # Apos isso ele manda para a camada de cima a resposta
        self.send_up(msg)
        pass


    def handle_segment_size_request(self, msg):
        '''Depois da camada de cima receber a primeira resposta, ela vai solicitar os seguimentos. Nesse caso vai cair aqui'''
        # Como esta solicitando o primeiro seguimento, vai cair nessa condicional
        if self.inicial:
            self.inicial -= 1
        
        # Ele cai nesse else caso seja a segunda solicitação de seguimento
        else:
            # Usando uma média das últimas probabilidades para decisões mais estáveis
            avg_prob = sum(self.listP[-5:]) / min(len(self.listP), 5)
            # Aqui ele vai avaliar o tamanho do buffer, caso o buffer seja pequeno, ele vai comparar
            # as duas ultimas probabilidades registradas. Caso a probabilidade penultima seja maior q a ultima
            # ele vai diminuir a qualidade em 1
            if self.whiteboard.get_amount_video_to_play() < 10:  # Buffer pequeno
                if avg_prob < self.listP[-1]:
                    # Aqui ele ira verificar se a qualidade é maior que 0, pois 0 é a menor qualidade possivel.
                    if self.qualidadeAtual > 0:
                        self.qualidadeAtual -= 1
            # Caso contrario ele ira verificar se o buffer esta maior que 10 e se a probabilidade é maior que 0,6,
            # se sim ele vai aumentar a qualidade em 1, pois significa que o buffer esta grande e que a conecção esta estavel.
            elif self.whiteboard.get_amount_video_to_play() > 15 and avg_prob > 0.6:
                # Aqui ele irá verificar se a qualidade não é maior que 19, pois 19 é a ultima qualidade da lista.
                if self.qualidadeAtual < 19:
                    self.qualidadeAtual += 1
        
        # Marcar o tempo inicial do request
        self.request_time = time.perf_counter()
        # Depois que fazer as verificações, ele vai guardar a probabilidade na lista
        self.listP.append(self.p)
        # vai guardar as qualidade no historico
        self.historicoQualidades.append(self.qualidadeAtual)
        # vai adicionar a qualidade definida na mensagem, e
        msg.add_quality_id(self.qi[self.qualidadeAtual])
        # por fim, ira mandar a mensagem com a qualidade escolhida para a camada de baixo
        self.send_down(msg)


   



    def handle_segment_size_response(self, msg):
        '''Quando a mensagem subir da camada de baixo, com o seguimento, ela cai aqui, onde vai ser calculado o touroughputs
        para a proxima solicitação'''
        # Quando a camada de baixo mandar a mensagem para cima, ele ira ver o tamanho da mensagem, 
        # para posteriormente calcular o touroughputs
        self.segment_size_response = msg.get_bit_length()

        # Primeiro ele ira validar a mensagem
        if msg.found():
            # aqui sera calculado a diferença do tempo da requisição
            elapsed_time = time.perf_counter() - self.request_time

            # Apos calcular, sera verificado se o essa difereça é maior que 0(em teoria, é pra em todos os casos ser mairo que 0)
            # essa validação é importante para não existir uma divisão por zero, e nem negatica, coisa que não faz sentido
            if elapsed_time > 0:
                # Calcular o touroughputs da mensagem solicitada
                measured_throughput = msg.get_bit_length() / elapsed_time
                
                # Essa condicional serve para limitar os touroughputs a no maximo 50 dados, 
                # dados suficiente par ater uma noção da rede
                if len(self.throughput) < 50:
                    self.throughput.append(measured_throughput)
                # Caso ja tenha 50 dados, sera removido o primeiro adicionado, e colocara o novo ao final
                else:
                    del self.throughput[0]
                    self.throughput.append(measured_throughput)


        # Essa parte foi criada fielmente segundo o artigo. As partes anteriores foram adicionada para melhorar o codigo
        # Primeiro é definido a media do touroughput em 0
        mediaThroughput = 0
        items = self.throughput
        
        # aqui sera calculado a media do touroughputs
        for i in range(1, len(items)+1):
            mediaThroughput += items[i-1]
        if items:
            mediaThroughput = mediaThroughput/(len(items))

        # Depois de calcular a media do touroughputs, aqui iremos aplicar o peso, para da preferencia
        # pros touroughputs masi recentes
        mediaThroughput_pesos = 0
        for i in range(1, len(items)+1):
            mediaThroughput_pesos += abs(items[i-1]-mediaThroughput) * (i / len(items))
        if items:
            mediaThroughput_pesos = mediaThroughput_pesos/(len(items))
        
        # Depois de calcular a media do touroughputs, e a media do touroughputs com os pesos, 
        # foi verificado se a soma dos dois é maior que zero
        # Essa condicional serve para quando for calculado a probabilidade da mudança, não seja dividido por zero.
        if (mediaThroughput + mediaThroughput_pesos) > 0:
            self.p = mediaThroughput/(mediaThroughput + mediaThroughput_pesos) 
        
        # essa probabilidade é calculada para o proximo seguimento, se baseando na solicitação anterior.
        # apos finalizar tudo isso, a mensagem sobe para a camada de cima.
        self.send_up(msg)
        




    def initialize(self):
        SimpleModule.initialize(self)
        pass


    def finalization(self):
        SimpleModule.finalization(self)
        pass