import os

import requests
import json

import datetime

import jwt

from time import time

from flask import Flask, request, abort
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, PostbackEvent, QuickReply, QuickReplyButton, PostbackAction,
    RichMenu, RichMenuArea,RichMenuBounds, RichMenuSize, StickerSendMessage)

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

rich_menu_to_create = RichMenu(
    size = RichMenuSize(width=2500, height=900),
    selected = True,
    name = 'richmenu',
    chat_bar_text = 'メニュー',
    areas=[
        RichMenuArea(
            bounds=RichMenuBounds(x=0, y=0, width=1273, height=900),
            action=PostbackAction(data='登録')
        ),
        RichMenuArea(
            bounds=RichMenuBounds(x=1278, y=0, width=1211, height=900),
            action=PostbackAction(data='確認')
        ),
    ]
)
richMenuId = line_bot_api.create_rich_menu(rich_menu=rich_menu_to_create)

with open('./img/select.png', 'rb') as f:
        line_bot_api.set_rich_menu_image(richMenuId, 'image/png', f)

line_bot_api.set_default_rich_menu(richMenuId)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']

    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(PostbackEvent)
def on_postback(event):
    data = event.postback.data
    user_id = event.source.user_id

    try:
        Session.get_state(user_id)
    except KeyError:
        Session.put_state(user_id, State())

    if Session.get_state(user_id) == 0 and data == '登録':
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="名前は？"))
        Session.set_state(user_id, 1)
    elif Session.get_state(user_id) == 0 and data == '確認':
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="検索したい名前は？"))
        Session.set_state(user_id, 5)
    elif Session.get_state(user_id) == 2:
        Session.set_status(user_id, data)
        if data == "退勤":
            Session.set_task(user_id, "")
            name = Session.get_name(user_id)
            status = Session.get_status(user_id)
            task = Session.get_task(user_id)
            ### 登録処理を書く
            put_data(name, status, task, user_id)
            Session.set_state(user_id, 0)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="お疲れさまでした!!!"))
        elif data == "離席中":
            Session.set_task(user_id, "")
            name = Session.get_name(user_id)
            status = Session.get_status(user_id)
            task = Session.get_task(user_id)
            text = f'***\n名前 : {name}\nタスク : {task}\nステータス : {status}\n***\nで登録しておいたよ.'
            ### 登録処理を書く
            put_data(name, status, task, user_id)
            Session.set_state(user_id, 0)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=text))
        else:
            line_bot_api.reply_message(event.reply_token, make_select_message_quick_task())
            Session.set_state(user_id, 3)
    elif Session.get_state(user_id) == 3:
        if data == 'その他':
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="その他を選択しました。内容は？"))
            Session.set_state(user_id, 6)
        else:
            Session.set_task(user_id, data)
            line_bot_api.reply_message(event.reply_token, make_select_message_quick_yes_no())
            Session.set_state(user_id, 4)
    elif Session.get_state(user_id) == 4:
        if data == 'Yes':
            name = Session.get_name(user_id)
            status = Session.get_status(user_id)
            task = Session.get_task(user_id)
            text = f'***\n名前 : {name}\nタスク : {task}\nステータス : {status}\n***\nで登録しておいたよ.'
            ### 登録処理を書く
            put_data(name, status, task, user_id)
        else:
            text = 'もう一度入力してね．'
        
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=text))
        Session.set_state(user_id, 0)

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):

    message = event.message.text
    user_id = event.source.user_id

    try:
        Session.get_state(user_id)
    except KeyError:
        Session.put_state(user_id, State())

    if Session.get_state(user_id) == 1:
        Session.set_name(user_id, message)
        line_bot_api.reply_message(event.reply_token, make_select_message_quick())
        Session.set_state(user_id, 2)
    elif Session.get_state(user_id) == 6:
        Session.set_task(user_id, message)
        line_bot_api.reply_message(event.reply_token, make_select_message_quick_yes_no())
        Session.set_state(user_id, 4)
    elif Session.get_state(user_id) == 5:
        reply_message, status, user_id_2 = convert_data(message)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_message))
        
        if status == '会議ok':
            # 会議OK
            meeting_text = createMeeting()
            line_bot_api.push_message(user_id, StickerSendMessage(package_id=789,sticker_id=10861))
            line_bot_api.push_message(user_id, TextSendMessage(text=meeting_text))
            line_bot_api.push_message(user_id_2, TextSendMessage(text=f"{get_name_from_kintone(user_id)}さんが会議をしたがっています。"))
            line_bot_api.push_message(user_id_2, TextSendMessage(text=meeting_text))
        elif status == 'チャットok':
            # 質問OK
            line_bot_api.push_message(user_id, StickerSendMessage(package_id=789,sticker_id=10858))
            line_bot_api.push_message(user_id_2, TextSendMessage(text=f"{get_name_from_kintone(user_id)}さんが質問をしたがっています。"))
        else:
            # 忙しい、離席中とか
            line_bot_api.push_message(user_id, StickerSendMessage(package_id=789,sticker_id=10860))
            questionOKPeople = getQuestionOKPeople("https://0kqan9y2mg9d.cybozu.com/k/v1/records.json?app=1","lnl2Tbtwiy2i8QR4kMGMgCd4llv3thiccjpvcda6")
            questionOKPeopleStr = "会議ok・チャットokな人一覧\n"
            print(questionOKPeople)
            for i in range(min(len(questionOKPeople),10)):#10人以上は表示しない
                questionOKPeopleStr += questionOKPeople[i]

                if i+1 != range(min(len(questionOKPeople),10)):
                    questionOKPeopleStr += "\n"
            line_bot_api.push_message(user_id, TextMessage(text=questionOKPeopleStr))

        Session.set_state(user_id, 0)
    else:
        help_message = '更新 : 流れに沿って更新\n確認 : 名前で状況確認'
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_message))

def quick_task():
    URL = 'https://0kqan9y2mg9d.cybozu.com/k/v1/records.json?app=6'
    API_TOKEN = "6Co5RtRSZXPVU3dopGMz8mDe4rxTngrXIrzpHbMv"

    RESP = get_kintone(URL, API_TOKEN)
 
    data = RESP.text
    
    #jsonファイルを辞書型に
    data = json.loads(data)
    
    data = data['records']
    
    statuses = []
    
    for d in data:
        statuses.append(d['name']['value'])
    
    return statuses

def getQuestionOKPeople(URL,API_TOKEN):

    RESP = get_kintone(URL, API_TOKEN)

    data = RESP.text

    #jsonファイルを辞書型に

    data = json.loads(data)

    data = data['records']

    #質門okの人の配列

    questionOkPeople = []

    for d in data:

        if d['status']['value'] != '忙しい' and d['status']['value'] != '離席中' and d['status']['value'] != '退勤':

            questionOkPeople.append(d['name']['value'])

    return questionOkPeople

def get_status():
    URL = 'https://0kqan9y2mg9d.cybozu.com/k/v1/records.json?app=5&id=1'
 
    API_TOKEN = "CzQiFvVr7AiItXTNp89lreRnzQpjmgAZvUI0KQ2d "

    RESP = get_kintone(URL, API_TOKEN)
    
    data = RESP.text
    
    #jsonファイルを辞書型に
    data = json.loads(data)
    
    data = data['records']
    
    statuses = []
    
    for d in data:
        statuses.append(d['name']['value'])

    return statuses

    
def get_kintone(url, api_token):
    """kintoneのレコードを1件取得する関数"""
    headers = {"X-Cybozu-API-Token": api_token}
    resp = requests.get(url, headers=headers)

    return resp

def make_select_message_quick_task():
    print(get_status())
    return TextSendMessage(
                    text='タスクは？',
                    quick_reply=QuickReply(items=[ QuickReplyButton(action=PostbackAction(label=state, data=state, display_text=state)) for state in quick_task()]))

def make_select_message_quick():
    print(get_status())
    return TextSendMessage(
                    text='今の状況は？',
                    quick_reply=QuickReply(items=[ QuickReplyButton(action=PostbackAction(label=state, data=state, display_text=state)) for state in get_status()]))

def make_select_message_quick_yes_no():
    return TextSendMessage(
                    text='この情報でいい？',
                    quick_reply=QuickReply(
                                    items=[
                                    QuickReplyButton(
                                        action=PostbackAction(label="Yes", data="Yes")
                                    ),
                                    QuickReplyButton(
                                        action=PostbackAction(label="No", data="No")
                                    ),
                                    ]))

def put_data(name, status, task, user_id):
    URL = 'https://0kqan9y2mg9d.cybozu.com/k/v1/record.json?app=1'
    API_TOKEN = "lnl2Tbtwiy2i8QR4kMGMgCd4llv3thiccjpvcda6"
    PARAMS = {
        "app": 1,
        "updateKey":{
            "field":"name",
            "value":name
        },
        "record": {
        "status":{
            "value":status
        }
        ,"task":{
            "value":task
        }
        ,"line_id":{
            "value": user_id
        },
        }
    }

    RESP = post_kintone(URL, API_TOKEN, PARAMS)
    print(RESP.text)

def get_name_from_kintone(query_id):
    URL = "https://0kqan9y2mg9d.cybozu.com/k/v1/records.json?app=1"
    API_TOKEN = "lnl2Tbtwiy2i8QR4kMGMgCd4llv3thiccjpvcda6" 
    RESP = get_kintone(URL, API_TOKEN)

    data = RESP.text
    
    #jsonファイルを辞書型に
    data = json.loads(data)
    
    data = data['records']
    
    #各データとansの照会
    want = ''
    for d in data:
        if d['line_id']['value'] == query_id:
            want = d
    if want == '':
        return str(query_id)
    else:
        return want['name']['value']

def convert_data(query_name):
    URL = "https://0kqan9y2mg9d.cybozu.com/k/v1/records.json?app=1"
    API_TOKEN = "lnl2Tbtwiy2i8QR4kMGMgCd4llv3thiccjpvcda6" 
    RESP = get_kintone(URL, API_TOKEN)

    data = RESP.text
    
    #jsonファイルを辞書型に
    data = json.loads(data)
    
    data = data['records']
    
    ans = query_name
    
    #各データとansの照会
    want = ''
    for d in data:
        if d['name']['value'] == ans:
            want = d
    if want == '':
        return '人が見つからなかったよ...'
    else:
        user_id = want['line_id']['value']
        name = want['name']['value']
        task = want['task']['value']
        status = want['status']['value']
        update_time = want['更新日時']['value'].replace('T', ' ').replace('Z', '')
        elapsed_time = datetime.datetime.now() - datetime.datetime.strptime(update_time, '%Y-%m-%d %H:%M:%S')
        hour, minutes, seconds = get_h_m_s(elapsed_time)
        print(want)

        return f'名前 : {name}\nタスク : {task}\nステータス : {status}\n経過時間 : {hour}時間{minutes}分 経過', status,  user_id

def get_kintone(url, api_token):
    headers = {"X-Cybozu-API-Token": api_token}
    resp = requests.get(url, headers=headers)
 
    return resp

def post_kintone(url, api_token, params):
    """kintoneにレコードを1件登録する関数"""
    headers = {"X-Cybozu-API-Token": api_token, "Content-Type" : "application/json"}
    resp = requests.put(url, json=params, headers=headers)
 
    return resp

def get_h_m_s(td):
    m, s = divmod(td.seconds, 60)
    h, m = divmod(m, 60)
    return h, m, s
 
# create a function to generate a token
# using the pyjwt library
 
def generateToken():
    # Enter your API key and your API secret
    API_KEY = '4Z7panFhQ4Cf7KTMTohQNA'
    API_SEC = 'GKF1I35qkEmsu1MCTPwRVRlg9zofNqSkuOT9'

    token = jwt.encode(
 
        # Create a payload of the token containing
        # API Key & expiration time
        {'iss': API_KEY, 'exp': time() + 5000},
 
        # Secret used to generate token signature
        API_SEC,
 
        # Specify the hashing alg
        algorithm='HS256'
    )
    return token.encode().decode('utf-8')
 
# send a request with headers including
# a token and meeting details
 
def createMeeting():
    # create json data for post requests
    meetingdetails = {"topic": "The title of your zoom meeting",
                        "type": 2,
                        "start_time": "2019-06-14T10: 21: 57",
                        "duration": "45",
                        "timezone": "Europe/Madrid",
                        "agenda": "test",
        
                        "recurrence": {"type": 1,
                                        "repeat_interval": 1
                                        },
                        "settings": {"host_video": "true",
                                    "participant_video": "true",
                                    "join_before_host": "False",
                                    "mute_upon_entry": "False",
                                    "watermark": "true",
                                    "audio": "voip",
                                    "auto_recording": "cloud"
                                    }
                     }

    headers = {'authorization': 'Bearer ' + generateToken(),
            'content-type': 'application/json'}
    r = requests.post(
        f'https://api.zoom.us/v2/users/me/meetings',
        headers=headers, data=json.dumps(meetingdetails))
 
    print("\n creating zoom meeting ... \n")
    # print(r.text)
    # converting the output into json and extracting the details
    y = json.loads(r.text)
    join_URL = y["join_url"]
    meetingPassword = y["password"]
 
    return f'\n here is your zoom meeting link {join_URL} and your password: "{meetingPassword}"\n'

class State:
    def __init__(self):
        self.state = 0
        self.name = ''
        self.status = ''
        self.task = ''
    
    def get_state(self):
        return self.state

    def set_state(self, state):
        self.state = state

    def get_name(self):
        return self.name

    def set_name(self, name):
        self.name = name

    def get_status(self):
        return self.status

    def set_status(self, status):
        self.status = status

    def get_task(self):
        return self.task

    def set_task(self, task):
        self.task = task

class Session:
    state_map = {}

    def put_state(user_id, state):
        Session.state_map[user_id] = state

    def get_state(user_id):
        return Session.state_map[user_id].get_state()

    def set_state(user_id, state):
        Session.state_map[user_id].set_state(state)

    def set_name( user_id, name):
        state = Session.state_map[user_id]
        state.set_name(name)
        Session.set_state(user_id, state)

    def get_name(user_id):
        state = Session.state_map[user_id]
        return state.get_name()

    def set_task( user_id, task):
        state = Session.state_map[user_id]
        state.set_task(task)
        Session.set_state(user_id, state)

    def get_task(user_id):
        state = Session.state_map[user_id]
        return state.get_task()

    def set_status(user_id, status):
        state = Session.state_map[user_id]
        state.set_status(status)
        Session.set_state(user_id, state)

    def get_status(user_id):
        state = Session.state_map[user_id]
        return state.get_status()


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)