from datetime import datetime

class ConsoleWriter():
    def __init__(self, gui, attr_name) -> None:
        self.attr  = getattr(gui, attr_name)

        self.string = ""

    def write(self, log):
        date_time = datetime.now()
        current_time = str(date_time).split(' ')[1].split(".")[0]
        
        lines = self.string.split("\n")
        n_lines = len(lines)

        self.string = current_time + ": " + log + "\n" + '\n'.join(self.string.split("\n")[0:min(n_lines, 11)]) 
        
        # new lines are being added to the top of the console rather than the bottom
        # cant be arsed to rethink logic so ill split the string and reverse the list before rejoining
        output = "\n".join(self.string.split("\n")[::-1])

        self.attr.set(output[1:])