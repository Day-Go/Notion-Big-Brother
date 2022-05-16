import json
import time
import keyboard
from threading import Timer
from notion.block import TextBlock, DividerBlock, HeaderBlock
from utils import get_date_and_time

# TO DO: ADD CTRL MOVEMENT KEYS

class KeyLogger():
    def __init__(self, gui, attr_list, database_entry, interval=60) -> None:
        self.database_entry = database_entry

        attr_dict = {}
        for attr in attr_list:
            attr_dict.update({attr: getattr(gui, attr)})

        self.console_writer = attr_dict["console_writer"]

        self.stopped = False
        self.interval = interval

        self.log = {0: ""}          # used to store and load lines of text
        self.line = ""              # line at current index
        self.line_buffer = ""       # output buffer

        self.w = {0: 0} # width of lines in the log
        self.h = 0      # number of rows '        '

        self.x = 0      # keeps track of text cursor (caret) horizontal position
        self.y = 0      # '                                ' vertical position

        self.ctrl = False   # is 'ctrl' being held down?
        self.shift = False  # is 'shift' being held down?

        time.sleep(2)

        self.search_for_header_block()

        if self.header_block is None:
            self.create_header_block()

    def main_loop(self, gui, attr_name):
        self.gui_attr = getattr(gui, attr_name)
        while not self.stopped:
            keyboard.on_press(callback=self.key_press_callback)

            # start reporting the logs
            self.write_log()

            # block the main thread, wait until CTRL+C is pressed
            keyboard.wait()

    def key_press_callback(self, event):
        name = event.name   

        # catch weird exceptions where python keyboard module is reading character keys
        # even though function keys are being pressed. i.e. f1 = "D"
        if name.isascii() and len(name) == 1:
            # check UTF-8 encoding -> 65 = "A", 90 = "Z"
            # if we get a key in that range and shift is NOT pressed, we have a problem
            if ord(name) >= 65 and ord(name) <= 90 and not keyboard.is_pressed("shift"):
                name = ""

        # convert event name to inline character
        key = self.event_name_to_key(name)

        if name == "backspace":
            offset = -1
        elif name == "delete":
            offset = 1
        else:
            offset = 0

        # only insert key into line if ctrl is not being pressed
        if not keyboard.is_pressed('ctrl'):
            self.insert_key_at_caret(key, offset)
        
        # perform key function and move caret
        self.execute_key_behaviour(name)

        gui_string = json.dumps(self.log)
        # gui_string = gui_string.replace("{","").replace("}","").replace("\"","").replace("\n"," ")

        self.gui_attr.set(gui_string)


    def search_for_header_block(self):
        self.header_block = None
        self.header_title = "Key log"

        for child in self.database_entry.children:
            # use nested if statements since not all children have a title attribute
            if isinstance(child, HeaderBlock):
                if child.title == self.header_title:
                    self.header_block = child

    def create_header_block(self):
        self.header_block = self.database_entry.children.add_new(HeaderBlock)
        self.header_block.title = self.header_title  

    def event_name_to_key(self, name):
        if len(name) == 1:
            # inline representation is the same as event name 
            key = name 
        elif name == "space":
            key = " " 
        elif name == "enter":
            key = "\n"
        elif name == "tab":         
            key = "\t"
        else:
            # all other special keys have no inline effect
            key = ""      

        return key

    def split_string_at_caret(self, offset):
        # split the string in half at caret x position
        lhs = self.line[:max(0, self.x+offset)]    # max() -> avoid -1
        rhs = self.line[self.x:]

        return lhs, rhs   

    def insert_key_at_caret(self, key, offset):
        lhs, rhs = self.split_string_at_caret(offset)

        # put together string with most recent keypress inserted
        self.line = lhs + key + rhs
        self.log.update({self.y: self.line})

    def calculate_jump_size(self, direction: str):
        jump_size = 0
        if direction == "left":
            half, _ = self.split_string_at_caret(0)
            idx = -1
        else:
            _, half = self.split_string_at_caret(0)
            idx = 0

        words = half.split(" ")

        if words[idx] == "":
            jump_size += 1
            words = list(filter(None, words))

        jump_size += len(words[-1])

        return jump_size

    def execute_key_behaviour(self, name):
        # TO-DO: Add shortcuts to caret behaviour (i.e. ctrl + left)
        self.ctrl = keyboard.is_pressed('ctrl')
        self.shift = keyboard.is_pressed('shift')

        # regular character pressed
        if len(name) == 1:
            self.x += 1

        # special character pressed
        else:
            if name == "space":
                self.x += 1
            elif name == "enter":
                self.enter()
            elif name == "backspace":
                self.backspace()
            elif name == "tab":
                pass
            elif name == "up":
                self.up()
            elif name == "down":
                self.down()
            elif name == "left":
                self.left()
            elif name == "right":
                self.right()
            elif name == "page up":
                pass
            elif name == "page down":
                pass

        self.update_text_field_size(self.log)

    def enter(self):
        # add new row to log and text field width dictionary
        if self.y < len(self.log):
            self.shift_rows(1) 

            # if caret is at the end of the line
            if self.x == len(self.log[self.y]):
                self.line = ""
            else:
                # split string to get chars on rhs of caret
                lhs, rhs = self.split_string_at_caret(0)    # <- offset = 0
                self.line = rhs.strip('\n')                 # copy rhs string to next line
                self.log.update({self.y: lhs+"\n"})         # shorten current line & add newline            

        else:

            self.line = ""

        self.x = 0
        self.y += 1

        # copy data to new line
        self.log.update({self.y: self.line})
        self.w.update({self.y: len(self.line)})

    def backspace(self):
        # if cursor is at the start of the line AND caret not on line 0
        if self.x == 0 and self.y != 0:
            buffer = self.log[self.y]
            self.y -= 1
            self.shift_rows(-1)
            # shift caret to end of previous line
            self.x = len(self.log[self.y].strip("\n"))
            # strip newline character from previous line + append buffered line to new line
            self.log[self.y] = self.log[self.y].strip("\n") + buffer
            self.line = self.log[self.y]
        else:
            # move caret one index to the left but not into negative values
            self.x = max(0, self.x - 1)

    def shift_rows(self, direction):
        # shift down 
        if direction == 1:
            # iterate backwards through log indicies to avoid overwriting text
            for row in range(len(self.log)-1, self.y-1, -1):
                # shift terms in dictionaries to the right by one
                self.log.update({row+direction: self.log[row]})
                self.w.update({row+direction: self.w[row]})
            self.h += 1
        # shift up
        else:
            for row in range(self.y+2, len(self.log)):
                self.log.update({row+direction: self.log[row]})
                self.w.update({row+direction: self.w[row]})
            # delete empty lines at the end of log
            if self.log[self.h] == "\n":
                self.log.pop(self.h)
                self.w.pop(self.h)
                self.h -= 1

    def up(self):
        # cant go up a line when you are at line zero
        if self.y != 0:
            self.line = self.log[self.y-1].strip("\n")

        self.log[self.y] += "\n"

        # caret cannot move to negative values
        self.y = max(0, self.y - 1)
        # when changing lines x position should not exceed width of the new line
        self.x = min(self.x, self.w[self.y])

    def down(self):
        # cant go down if row = length of log dictionary
        # NOTE: we do self.y+1 because caret index starts at 0 but len(self.log) starts at 1
        if self.y+1 != len(self.log):
            self.line = self.log[self.y+1].strip("\n") 

        self.log[self.y] += "\n"

        # caret cannot move beyond the height of the text field 
        self.y = min(self.h, self.y + 1)
        # when changing lines x position should not exceed width of the new line
        self.x = min(self.x, self.w[self.y])

    def left(self):
        
        # if caret is at the start of the line AND not on row 0
        if self.x == 0 and self.y != 0:
            self.log[self.y] += "\n"
            self.y -= 1
            self.line = self.log[self.y].strip("\n")    # load previous line

            self.x = len(self.log[self.y])-1

            if self.ctrl:
                jump_size = len(self.line.split(" ")[-1])
                self.x = len(self.log[self.y])-(jump_size+1)
            else:
                self.x = len(self.log[self.y])-1            # position caret at end of the line
        
        else:
            if self.ctrl:
                jump_size = self.calculate_jump_size("left")
                self.x = max(0, self.x - jump_size)
            else:
                self.x = max(0, self.x - 1)

    def right(self):
        # if caret is at the end of the line AND not the final row
        if self.x == len(self.log[self.y]) and self.y != self.h:
            self.log[self.y] += "\n"
            self.y += 1
            self.line = self.log[self.y].strip("\n")    # load next line
            self.x = 0

            if self.ctrl:
                jump_size = len(self.line.split(" ")[0])
                self.x += jump_size
            else:
                self.x = len(self.log[self.y])-1            # position caret at end of the line
        
        else:
            if self.ctrl:
                jump_size = self.calculate_jump_size("right")
                self.x = min(self.w[self.y], self.x + jump_size)
            else:
                # caret cannot move beyond where characters already exist
                self.x = min(self.w[self.y], self.x + 1)
    
    def reset(self):
        # initialise new timer object that calls function after interval (seconds)
        timer = Timer(interval=self.interval, function=self.write_log)
        timer.daemon = True
        timer.start()

    def write_log(self):
        """
        This function gets called every `self.interval`
        It sends keylogs to notion and resets `self.log` variable
        """
        _, self.time = get_date_and_time()
        
        self.console_writer.write("key buffer is ready to be emptied. Press enter.")

        # the log is written to notion after a certain interval of time, but 
        # we don't want lines to be abruptly cut in half so we wait for the user
        # to type a newline. i.e. the enter key
        keyboard.wait('enter')

        for line in self.log.values():
            if not "\n" in line:
                line += "\n" 
            self.line_buffer += line

        self.x, self.y = 0, 0
        self.w, self.h = {0:0}, 0

        self.log = {}
        self.line = ""
        
        self.console_writer.write("Uploading key buffer to notion.")

        if len(self.line_buffer) > 5:
            self.database_entry.children.add_new(DividerBlock)
            self.database_entry.children.add_new(TextBlock, title=self.time)
            self.database_entry.children.add_new(TextBlock, title=self.line_buffer)

        self.line_buffer = ""

        self.reset()

    def update_text_field_size(self, log):
        # get highest value out of selected rows width and caret x position
        temp = max(self.x, len(log[self.y]))

        # update width and height of text field
        self.h = max(self.h, self.y)
        self.w.update({self.y: temp})
