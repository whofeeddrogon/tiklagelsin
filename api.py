URL = 'http://5456715068009545.eu-central-1.pai-eas.aliyuncs.com/'
ENDPOINT = 'api/predict/manuelabem_revised'
KEY = 'YTJkYWNjNjc0YjgyNjBmYzI5NTM5MTAwZTk3ZGM4N2FjMjhkMzQ5OA=='

import requests
from enum import Enum

class Label(Enum):
    NON = 0
    TOXIC = 1

class Response:
    label: Label
    conf: float
    def __init__(self, json):
        data = json['data'][0]
        self.label = Label.NON if data['label'] == 'NON_TOXIC' else Label.TOXIC
        self.conf = data['confidences'][0]['confidence']

    def get_label(self) -> Label:
        return self.label

    def get_conf(self) -> float:
        return self.conf
    
    def __resp__(self):
        return f'Response is {self.label} with confidence {self.conf}'

def send_comment(comment: str) -> Response:
    body = {
        'data': [comment]
    }
    x = requests.post(URL + ENDPOINT, json= body, headers= {'Authorization': KEY})
    return Response(x.json())

def test():
    resp = send_comment('yemekler çok güzel olmuş yapanın eline sağlık')
    print(resp.__resp__())

if __name__ == '__main__':
    test()