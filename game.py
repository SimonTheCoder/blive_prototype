
#encoding=utf8

from flask import Flask, request
import threading
import tkinter as tk
from tkinter import ttk
import requests
import json
import markdown
import time

# from tkinterhtml import HtmlFrame

global_delay = 3 #seconds
app = Flask(__name__)
server_ip = "192.168.1.66:4001"

class GuiThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def get_story(self, selection = None):
        self.enable_selection = False
        if selection  is None:
            # init the game.
            game_prompt = """我们来玩一个桌面文字RPG游戏。
            由你来生成剧情，在一段剧情结束后，给我三个选项。
            然后我会选出一个选项。之后你根据前面的剧情以及我的选项继续生成剧情，并提出三个新的选项。
            如此往复，直到我说：游戏结束。
            """

        else:
            game_prompt = f"{selection}"

        url = "http://" + server_ip + "/message/" + "RGP_Game2"
        headers = {'Content-Type': 'application/json; charset=utf-8'}
        data = {
            "message": game_prompt
        }
        print("Asking AI game master about:"+game_prompt)
        response = requests.post(url, headers=headers, json=data)
        print(f"AI response = {response.text}")
        text = json.loads(response.text).get("response")
        while text is None:
            print("AI request error. retry")
            time.sleep(30)
            response = requests.post(url, headers=headers, json=data)
            print(f"AI response = {response.text}")
            text = json.loads(response.text).get("response")


        # html = markdown.markdown(text)
        # self.story_text.delete('1.0', tk.END)
        # self.story_text.insert(tk.END, html)
        # self.story_text.config(text=html)
        # self.story_text.set_content(html)
        self.story = text
        self.story_text.config(text=text)
        self.set_text(f"故事更新完成。")
        time.sleep(global_delay)
        self.enable_selection = True

    def run(self):
        self.root = tk.Tk()
        root = self.root
        self.enable_selection = False
        # frame = HtmlFrame(root, horizontal_scrollbar="auto")
 
        # frame.set_content("<html></html>")

        self.story_text =  tk.Label(root, text="story", wraplength=400, justify="left", font=("SimHei", 18))
        self.story_text.pack(padx=20, pady=10)
        #self.get_story()
        # create a separator
        separator = ttk.Separator(root, orient='horizontal')
        separator.pack(fill='x', padx=10, pady=10)
        self.label = tk.Label(self.root, text="",font=("SimHei", 13))
        self.label.pack(padx=20, pady=10)
        print(self.label)
        self.root.mainloop()

    def set_text(self, text):
        self.label.config(text=text)

gui_thread = GuiThread()
gui_thread.start()

@app.route('/msessage', methods=['POST'])
def receive_json():
    if gui_thread.enable_selection :
        gui_thread.enable_selection = False
        json_data = request.get_json()
        user_name = json_data['user_name']
        message = json_data['message']
        my_thread = threading.Thread(target=commit_selection, args=(user_name, message))
        my_thread.start()
        return "OK" 
    else:
        return "FAIL"   

def commit_selection(user_name, message):
    gui_thread.set_text(f"正在提交 {user_name} 的选择：{message} ...")
    gui_thread.get_story(message)   
    return "OK" 


@app.route('/select', methods=['POST'])
def receive_json_select():
    if gui_thread.enable_selection :
        # gui_thread.enable_selection = False
        json_data = request.get_json()
        user_name = json_data['user_name']
        message = json_data['message']
        print("user_name: " + user_name)
        if message in gui_thread.story or user_name == "LordSimon":
            my_thread = threading.Thread(target=commit_selection, args=(user_name, message))
            my_thread.start()
            return "OK" 
        else:
            print(f"{message}\nnot in story\n{gui_thread.story}.")
            return "FAIL"    
    else:
        return "FAIL"    


if __name__ == '__main__':
    gui_thread.get_story()
    gui_thread.set_text("连接AI game master... OK")
    app.run(debug=False)

# test cmd
# curl -X POST      -H "Content-Type: application/json"      -d '{"user_name": "Alice", "message": "1"}'      http://localhost:5000/select