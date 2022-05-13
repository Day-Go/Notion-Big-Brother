import time
import json
import keyboard
import configparser
from threading import Thread
import tkinter as tk
from tkinter import ttk

from notion_handler import Notion
from screen_tracker import ScreenTimeTracker
from key_logger import KeyLogger
from console_writer import ConsoleWriter


configs = configparser.ConfigParser()
configs.read('cfg.ini')

class App(tk.Tk):
    def __init__(self) -> None:
        self.window = super().__init__()

        # window config
        self.title("Big Brother: A notion integrated self-analysis tool")
        self.resizable(0, 0)

        # gui state
        self.params = {}
        self.running = False

        # App uses three objects - set to None to indicate that the objects need to be created
        self.notion = None
        self.screentime_tracker = None
        self.key_logger = None

        # create, populate and format gui
        self.load_default_params()
        self.create_frames()
        self.position_frames()
        self.add_config_input_widgets()
        self.add_start_button()
        self.add_settings_widgets()
        self.display_config()
        self.display_screentime_stats()
        self.display_key_log_buffer()
        self.display_console()

        self.console_writer = ConsoleWriter(self, "console_string")

    def load_default_params(self):
        section = "DEFAULT"
        for key in configs[section]:
            value = configs[section][key]

            self.params.update({key: value})

    def create_frames(self):
        border_params = dict(
            padx=5, pady=5,
            highlightbackground="gray", 
            highlightthickness=1
        )

        frm_cfg_input = tk.Frame(master=self.window)
        frm_cfg_disp = tk.Frame(master=self.window, **border_params)
        frm_start_btn = tk.Frame(master=self.window)
        frm_settings = tk.Frame(master=self.window, **border_params)
        frm_console = tk.Frame(master=self.window, bg="black", **border_params)
        frm_screentime = tk.Frame(master=self.window,  bg="white", **border_params)
        frm_key_logger = tk.Frame(master=self.window,  bg="white", **border_params)

        self.frames = {
            "cfg_input": frm_cfg_input,
            "cfg_disp": frm_cfg_disp,
            "start_btn": frm_start_btn,
            "settings": frm_settings,
            "console": frm_console,
            "screentime": frm_screentime,
            "key_logger": frm_key_logger
        }

    def position_frames(self):
        self.frames["cfg_input"].grid(row=0, column=0, columnspan=2, padx=15, pady=5)
        self.frames["cfg_disp"].grid(row=2, column=0, columnspan=2, pady=(0,15))
        self.frames["start_btn"].grid(row=1, column=1, pady=(5,15))
        self.frames["settings"].grid(row=1, column=0, pady=(5,15))
        self.frames["console"].grid(row=3, column=0, columnspan=4)
        self.frames["screentime"].grid(
            row=0, rowspan=3,
            column=2,
            padx=(5,15), pady=15,
            sticky="ns"
        )
        self.frames["key_logger"].grid(
            row=0, rowspan=3,
            column=3, columnspan=2,
            padx=(5,15), pady=15,
            sticky="ns"
        )

    def add_config_input_widgets(self):
        master = self.frames["cfg_input"]

        entry_params = dict(master=master, width=75)
        
        ent_root_url = tk.Entry(**entry_params)
        ent_db_name = tk.Entry(**entry_params)
        ent_tb_name = tk.Entry(**entry_params)

        self.cfg = {
            "root_url": ent_root_url,
            "db_name": ent_db_name,
            "tb_name": ent_tb_name,
        }

        labels = ["Root page URL", "Database name", "Summary table name"]

        # entries need to be packed after loading config dict otherwise the variables
        # are treated as already having the .get() method applied for some reason
        for idx, entry in enumerate(self.cfg.values()):
            tk.Label(master=master, text=labels[idx]).pack(anchor="w")
            entry.pack(pady=(0,5))

        self.cfg_btn = tk.Button(
            master=master,
            command=self.update_params,
            text="Configure notion workspace",
        )
        
        self.cfg_btn.pack(fill=tk.X, padx=50 ,pady=(5,10))
      
    def display_config(self):
        master = self.frames["cfg_disp"]

        tk.Label(
            master=master,
            text="Current configuration",
            width=60
        ).grid(row=0, column=0, columnspan=2, sticky="w")

        # this will become a pain  if more configurations get added later on
        self.cfg_disp_prefixes = [
            "Root page URL: ",
            "Database: ",
            "Table: "
        ]

        if len(self.params['root_url']) > 58:
            # truncate long strings
            string = f"{self.params['root_url'][0:54]}...\""
        else:
            string = self.params['root_url']

        self.param_fields = [
            string,
            self.params["db_name"],
            self.params["tb_name"]
        ]

        grid_kwargs = [
            dict(row=1, column=0, columnspan=2, sticky="w"),
            dict(row=2, column=0, sticky="w"),
            dict(row=2, column=1, sticky="w")
        ]

        self.cfg_disp_vars = [tk.StringVar() for _ in self.cfg_disp_prefixes]

        for idx, var in enumerate(self.cfg_disp_vars):
            var.set(self.cfg_disp_prefixes[idx] + self.param_fields[idx])
            tk.Label(
                master=master,
                text=var.get(),
                textvariable=var,
            ).grid(**grid_kwargs[idx])

    def add_start_button(self):
        master = self.frames["start_btn"]

        self.start_btn = tk.Button(
            master=master,
            command=self.init_program_threads,
            text="Start"
        )
        
        self.start_btn.pack(fill=tk.X, ipadx=25)

    def toggle_start_button_text(self):
        if self.running:
            self.start_btn["text"] = "Stop"
        else:
            self.start_btn["text"] = "Start"
 
    def add_settings_widgets(self):
        master = self.frames["settings"]

        labels = ["Screen time", "Key logger", "Save locally"]
        settings_var = [tk.BooleanVar() for _ in range(3)]

        self.settings = {}
        for idx, label in enumerate(labels):
            ttk.Checkbutton(
                master=master,
                text=label,
                variable=settings_var[idx]
            ).grid(row=0, column=idx, padx=5)

            self.settings.update({label: settings_var[idx]})

    def display_screentime_stats(self):
        tk.Label(
            master=self.frames["screentime"],
            text="Screentime",
            bg="white",
            width=14
        ).pack()

        self.screentime_stats = tk.StringVar()

        tk.Label(
            master=self.frames["screentime"],
            text=self.screentime_stats.get(),
            textvariable=self.screentime_stats,
            bg="white", fg="black"
        ).pack()

    def display_key_log_buffer(self):
        tk.Label(
            master=self.frames["key_logger"],
            text="Key buffer",
            bg="white",
        ).pack()

        self.key_log_buffer= tk.StringVar()

        tk.Label(
            master=self.frames["key_logger"],
            text=self.key_log_buffer.get(),
            textvariable=self.key_log_buffer,
            bg="white", fg="black",
            width=50, wraplength=320,
            justify=tk.LEFT,
        ).pack(padx=15, anchor="w")

    def display_console(self):
        tk.Label(
            master=self.frames["console"],
            text="Console:",
            font=('Courier', 11),
            fg="white", bg="black",
            anchor="w", width=116
        ).pack()

        self.console_string = tk.StringVar()

        self.console = tk.Label(
            master=self.frames["console"],
            text=self.console_string.get(),
            textvariable=self.console_string,
            font=('Courier', 10),
            height=12, width=128,
            fg="white", bg="black",
            anchor="nw", justify=tk.LEFT
        )

        self.console.pack()

    def update_params(self):
        self.console_writer.write("Updating program parameters.")
        for idx, (key, value) in enumerate(self.cfg.items()):
            # the gui mustnt grow horizontally depending on length of the url
            if len(value.get()) > 58:
                # truncate long strings
                string = f"{value.get()[0:54]}...\""
            else:
                string = value.get()

            self.params.update({key: value.get()})
            self.cfg_disp_vars[idx].set(
                self.cfg_disp_prefixes[idx] + string
            )

        for key, value in self.settings.items():
            self.params.update({key: value.get()})


    def init_program_threads(self):
        self.running = not self.running
        self.toggle_start_button_text()

        t1 = Thread(target=self.run_program)
        t1.start()

    def run_program(self):
        if self.notion is None: 
            self.console_writer.write("Creating notion workspace...")
            self.notion = Notion(self, ["params", "console_writer"])
            self.console_writer.write("Notion workspace ready!")

        if self.settings["Screen time"].get():
            t2 = Thread(target=self.run_screentime_tracker)
            t2.daemon = True
            t2.start()

        if self.settings["Key logger"].get():
            t4 = Thread(target=self.run_key_logger)
            t4.daemon = True
            t4.start()

    def run_screentime_tracker(self):
        if self.screentime_tracker is None:
            self.console_writer.write("Initializing screentime tracker...")
            self.screentime_tracker = ScreenTimeTracker(self, ["console_writer"], self.notion.database_entry)
            
        if self.running:
            self.screentime_tracker.stopped = False

            self.console_writer.write("Entering screentime tracker main loop.")
            self.screentime_tracker.main_loop(self, "screentime_stats")
        else:
            self.console_writer.write("Screentime tracker stopped.")
            self.screentime_tracker.stopped = True

    def run_key_logger(self):
        if self.key_logger is None:
            time.sleep(3)
            self.console_writer.write("Initializing key logger...")
            self.key_logger = KeyLogger(self, ["console_writer"], self.notion.database_entry)

        if self.running:
            self.key_logger.stopped = False
            self.console_writer.write("Entering key logger main loop...")
            self.key_logger.main_loop(self, "key_log_buffer")
        else:
            self.key_logger.stopped = True

if __name__ == "__main__":
    app = App()
    app.mainloop()

