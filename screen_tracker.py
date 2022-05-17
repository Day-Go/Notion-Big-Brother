import os
import re
import time
import win32gui
import win32process
import win32api
import win32con
import matplotlib.pyplot as plt
from threading import Thread
from notion.block import ImageBlock, HeaderBlock, ToggleBlock, TextBlock
from utils import get_date_and_time

def format_screentime_string(dict):
    string = str(dict)
    string = string.replace("{","").replace("}","").replace("'","").replace(",","\n").split("\n")
    string = "\n".join(string[::-1])
    return string

class ScreenTimeTracker():
    def __init__(self, gui, attr_list, database_entry) -> None:
        self.date, _ = get_date_and_time()

        self.database_entry = database_entry

        attr_dict = {}
        for attr in attr_list:
            attr_dict.update({attr: getattr(gui, attr)})

        self.console_writer = attr_dict["console_writer"]

        self.stopped = False
        self.paused = False
        self.process = None
        self.screentime_stats_secs = {}
        self.screentime_stats_mins = {}
        self.detailed_stats_secs = {}
        self.detailed_stats_mins = {}

        self.idle_time = 0
        self.ox, self.oy = 0, 0

        self.make_local_image_path()
        self.console_writer.write(f"Images will be saved locally to {self.path}")
        
        self.search_for_header_block()
        self.search_for_toggle_block()
        self.search_for_image_block()
        
        if self.header_block is None:
            self.create_header_block()
        if self.toggle_block is None:
            self.create_toggle_block()
        else:
            self.load_screentime_from_notion()
        if self.img_block is None:
            self.create_image_block()

        

    def main_loop(self, gui=None, attr_name=None):
        if gui is not None:
            self.attr  = getattr(gui, attr_name)
            idle_thread = Thread(target=self.check_if_idle)
            idle_thread.daemon = True
            idle_thread.start()

            upload_thread = Thread(target=self.upload_figure)
            upload_thread.daemon = True
            upload_thread.start()
        
        while not self.stopped and not self.paused:
            self.get_active_process_name()
            self.update_screentime_stats()
            self.update_detailed_stats()
            self.sort_screentime_stats()
            self.screentime_string = format_screentime_string(self.screentime_stats_secs)

            self.attr.set(self.screentime_string)
            
            time.sleep(1)

    def pause(self):
        self.console_writer.write(f"Screentime tracker was paused due to {self.idle_time} seconds of idle time.")
        self.paused = True
        self.check_if_idle()
        time.sleep(1)

    def resume(self):
        self.console_writer.write("Mouse movement detected. Screentime tracker resuming.")
        self.paused = False

        main_thread = Thread(target=self.main_loop)
        main_thread.daemon = True
        main_thread.start()

        upload_thread = Thread(target=self.upload_figure)
        upload_thread.daemon = True
        upload_thread.start()

        self.check_if_idle()
        
    def check_if_idle(self):
        while not self.stopped:
            x, y = win32api.GetCursorPos()
            # check if cursor has moved
            # x == self.ox and y == self.oy ---> hasn't moved!
            if x == self.ox and y == self.oy:
                self.idle_time = self.idle_time + 1
            # if it has moved and the program is paused, reset idle time and resume program
            elif self.paused:
                self.idle_time = 0
                self.resume()
            # otherwise just reset idle time
            else:
                self.idle_time = 0
                
            if self.idle_time >= 180 and not self.paused:
                self.pause()
            
            self.ox, self.oy = x, y
            time.sleep(1)
        
    def make_local_image_path(self):
        self.img_name = f'{self.date}-screentime.png'
        cwd = os.getcwd()
        self.path = os.path.join(cwd, "imgs",self.img_name)

    def search_for_header_block(self):
        self.header_block = None
        self.header_title = "Screen time summary"

        for child in self.database_entry.children:
            # use nested if statements since not all children have a title attribute
            if isinstance(child, HeaderBlock):
                if child.title == self.header_title:
                    self.header_block = child

    def search_for_toggle_block(self):
        self.toggle_block = None
        self.toggle_title = "Detailed overview"

        for child in self.database_entry.children:
            # use nested if statements since not all children have a title attribute
            if isinstance(child, ToggleBlock):
                if child.title == self.toggle_title:
                    self.toggle_block = child
                    self.detail_block = self.toggle_block.children[0]

    def search_for_image_block(self):
        self.img_block = None        
        self.img_caption = f"Screen time chart for {self.date}"

        for child in self.database_entry.children:
            # use nested if statements since not all children have a caption attribute
            if isinstance(child, ImageBlock):
                if child.caption == self.img_caption:
                    self.img_block = child

    def create_header_block(self):
        self.header_block = self.database_entry.children.add_new(HeaderBlock)
        self.header_block.title = self.header_title  

    def create_toggle_block(self):
        self.toggle_block = self.database_entry.children.add_new(ToggleBlock)
        self.toggle_block.title = self.toggle_title 
        self.detail_block = self.toggle_block.children.add_new(TextBlock)

    def create_image_block(self):
        self.img_block = self.database_entry.children.add_new(ImageBlock)
        self.img_block.caption = self.img_caption      

    def load_screentime_from_notion(self):
        for child in self.toggle_block.children:
            # ugly line -> first we remove all the whitespaces from the string
            # then we use a regular expression to split the string by multiple delimiters
            app_screentime_list = re.split('[:\n]', child.title.replace(" ",""))
            
            apps = app_screentime_list[0::2]
            screentimes = app_screentime_list[1::2]
            screentimes = [int(val) for val in screentimes]

            self.screentime_stats_secs = dict(zip(apps, screentimes))

    def get_active_tab_name(self, handle):
        title = win32gui.GetWindowText(handle)

        print(title)
        if "Twitter" in title:
            title = "Twitter"
        elif "Facebook" in title:
            title = "Facebook"
        elif "Reddit" in title:
            title = "Reddit"
        elif "CoinGecko" in title:
            title = "CoinGecko"
        elif "Notion" in self.process:
            pass
        else:
            title = re.split('[-—]',title)[:-1][::-1]
            title = title[0]
                
        self.tab_title = title.strip(" ")
        # if "Twitter" in title:
        #     title = title.split(":")[0]
        #     title = title.split('/')[0]
        # elif "Facebook" in title:
        #     title = title.split("|")[0]
        # elif "Notion" in self.process:
        #     pass
        # else:
        #     title = re.split('[-—]',title)[:-1][::-1]
       
    #    self.title = title
        print(title)

    def update_detailed_stats(self):
        if self.process in self.detailed_stats_secs.keys():
            app = self.detailed_stats_secs[self.process]
            if self.tab_title in app.keys():
                self.detailed_stats_secs[self.process].update({self.tab_title: self.detailed_stats_secs[self.process][self.tab_title] + 1})
                # self.detailed_stasts_secs.update({self.process: {self.tab_title: self.detailed_stats_secs[self.process][self.tab_title] + 1}})
            else:
                self.detailed_stats_secs[self.process].update({self.tab_title: 1})   
        else:
            self.detailed_stats_secs.update({self.process: {}})   

        print(self.detailed_stats_secs)

    def get_active_process_name(self):
        # getting occasional errors where the process handle is released between function
        # calls. doesnt happen ofter and has minimal effect on the code so i will handle
        # the error with zero fucks (for now)
        try:
            window_handle = win32gui.GetForegroundWindow()
            pid = win32process.GetWindowThreadProcessId(window_handle)
            process_handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid[1])
            process_path  = win32process.GetModuleFileNameEx(process_handle, 0)

            self.process = process_path.split('\\')[-1].split('.')[0].capitalize()

            self.get_active_tab_name(window_handle)
        except:
            pass

    def update_screentime_stats(self):
        if self.process in self.screentime_stats_secs.keys():
            self.screentime_stats_secs.update({self.process: self.screentime_stats_secs[self.process] + 1})
        else:
            self.screentime_stats_secs.update({self.process: 1})   

    def sort_screentime_stats(self):
        self.screentime_stats_secs = {k: v for k, v in sorted(self.screentime_stats_secs.items(), key=lambda item: item[1])}

    def upload_figure(self):
        minimum_use = 3
        while not self.stopped and not self.paused:
            time.sleep(15)

            self.detail_block.title = self.screentime_string

            self.convert_to_minutes()
            # self.remove_low_use_apps(minimum_use)  # dont include apps with less than 3 mins use time
            
            self.console_writer.write("Uploading screentime chart to notion.")

            # configure output figure style
            plt.style.use('dark_background')
            plt.grid(True)

            plt.barh(range(len(self.screentime_stats_mins)), list(self.screentime_stats_mins.values()), align='center')
            plt.yticks(range(len(self.screentime_stats_mins)), list(self.screentime_stats_mins.keys()))
            plt.title(f"Screen time - {self.date}")
            plt.ylabel("App name", fontsize=14)
            plt.xlabel("Time (m)", fontsize=14)
            plt.savefig(self.path, bbox_inches = 'tight')
            plt.close()

            # upload image to notion
            self.img_block.upload_file(self.path)

    def convert_to_minutes(self):
        self.screentime_stats_mins = {k: v / 60 for k, v in self.screentime_stats_secs.items()}

    def remove_low_use_apps(self, duration):
        self.screentime_stats_mins = {key:val for key, val in self.screentime_stats_mins.items() if val < duration}