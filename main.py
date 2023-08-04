# -*- coding:utf-8 -*-
# author:cchu4@iflytek.com
# @Time: 2023/7/12 17:09
import builtins
import keyword
import subprocess
# 导入tkinter模块用于GUI
import sys
import time
import tkinter as tk
# filedialog用于打开和保存文件对话框
from tkinter import filedialog, ttk, scrolledtext
from tkinter import messagebox
import tkinter.font


def _get_py_keywords():
    keywords = list(keyword.kwlist)
    builtin_functions = [item for item in dir(builtins) if callable(getattr(builtins, item))]
    keywords.extend(builtin_functions)
    return list(set(keywords))


class Tab:
    def __init__(self, tab, tab_file_path,
                 text_area, text_area_font,
                 line_number_canvas, status_bar,
                 output_area, find_status_label=None,
                 current_find_idx=None, all_match_cnt=0, cur_match_cnt=0):
        self.tab = tab
        self.tab_file_path = tab_file_path
        self.text_area = text_area
        self.text_area_font = text_area_font
        self.line_number_canvas = line_number_canvas
        self.status_bar = status_bar
        self.output_area = output_area
        self.find_status_label = find_status_label
        self.current_find_idx = current_find_idx
        self.all_match_cnt = all_match_cnt
        self.cur_match_cnt = cur_match_cnt


class AutocompleteText(tk.Text):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bind('<KeyRelease>', self.on_key_release)
        self.toplevel = tk.Toplevel(self.master)
        self.toplevel.withdraw()
        self.toplevel.overrideredirect(True)
        self.listbox = tk.Listbox(self.toplevel)
        self.listbox.pack()

    def on_key_release(self, event):
        if event.keysym == "Down":
            self.listbox.focus_set()
            self.listbox.select_set(0)
        elif event.keysym == "Escape":
            self.toplevel.withdraw()
        elif event.keysym.isalnum():
            viewable = self.update_list()
            bbox = self.bbox(self.index(tk.INSERT))
            if bbox and viewable:
                x, y, _, _ = bbox
                font = tkinter.font.Font(font=self.cget("font"))
                font_height = font.metrics('linespace')
                screen_x = self.winfo_rootx() + x
                screen_y = self.winfo_rooty() + y + font_height
                self.toplevel.geometry(f"+{screen_x}+{screen_y}")  # Move the toplevel window under the text widget
                self.toplevel.deiconify()  # Show the toplevel window

    def update_list(self):
        # 获取当前单词
        line, column = self.index(tk.INSERT).split('.')
        start = self.index(f'{line}.{int(column) - 1}')
        while start[0] == line and self.get(start) != ' ' and start.split(".")[1] != '0':
            start = self.index(f'{start.split(".")[0]}.{int(start.split(".")[1]) - 1}')
        all_input = self.get("1.0", tk.END)
        self.word = all_input.rsplit(' ', 1)[-1][:-1]
        # 更新 listbox 中的内容
        self.listbox.delete(0, tk.END)
        viewable = True
        if self.word and not self.word.isspace():
            matches = [kw for kw in _get_py_keywords() if kw.startswith(self.word)]
            if len(matches) == 0:
                self.toplevel.withdraw()
                viewable = False
            else:
                self.listbox.config(height=len(matches))
                for match in matches:
                    self.listbox.insert(tk.END, match)

                # Set the width of the listbox to 1.5 times the length of the longest matching word
                max_length = max(len(match) for match in matches)
                self.listbox.config(width=int(1.5 * max_length))
        else:
            self.toplevel.withdraw()
            viewable = False

        # 绑定 listbox 事件
        self.listbox.bind('<Double-Button-1>', self.on_select)
        self.listbox.bind('<Return>', self.on_select)
        return viewable

    def on_select(self, event):
        current_selection = self.listbox.curselection()
        if current_selection:
            self.insert(tk.INSERT, self.listbox.get(current_selection[0])[len(self.word):])
        self.toplevel.withdraw()


# 文本编辑器类
class TextEditor:
    def __init__(self, root):
        self.root = root
        self.tabs_mapping = {}
        root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=1)

        self.root.bind("<Control-n>", self.new_file)
        self.root.bind("<Control-s>", self.save_file)
        # 另存为
        self.root.bind("<Command-s>", lambda event: self.save_file(event, True))
        self.root.bind("<Control-w>", self.close_file)
        # 增大字体
        self.root.bind("<Control-l>", self.increase_font_size)
        # 缩小字体
        self.root.bind("<Control-k>", self.decrease_font_size)
        # 全选文本
        self.root.bind("<Control-a>", self.select_all)
        # 运行脚本
        self.root.bind("<Control-b>", self.run_script)
        # 每次键盘释放时，高亮显示关键字
        self.root.bind("<KeyRelease>", self.highlight_keywords)
        self.new_file()

        # 创建一个菜单栏
        self.menu = tk.Menu(root)
        # 设置root窗口的顶级菜单为self.menu
        root.config(menu=self.menu)
        # 在self.menu菜单中创建一个子菜单self.file_menu
        self.file_menu = tk.Menu(self.menu)
        # 添加一个名为"File"的下拉菜单，并设置它的子菜单为self.file_menu
        self.menu.add_cascade(label="File", menu=self.file_menu)
        # 在self.file_menu菜单中添加"Open"选项，点击后会调用self.open_file函数
        self.file_menu.add_command(label="Open", command=self.open_file)
        # 在self.file_menu菜单中添加"Save/Save As"选项，点击后会调用self.save_file函数
        self.file_menu.add_command(label="Save", command=self.save_file)
        self.file_menu.add_command(label="Save As...", command=lambda event: self.save_file(event, True))

        self.find_memu = tk.Menu(self.menu)
        self.menu.add_cascade(label="Find", menu=self.find_memu)
        self.find_memu.add_command(label="Find", command=self.display_find_box)

        self.edit_menu = tk.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="Edit", menu=self.edit_menu)
        self.font_menu = tk.Menu(self.edit_menu, tearoff=0)
        self.edit_menu.add_cascade(label="Font", menu=self.font_menu)
        self.font_size_menu = tk.Menu(self.font_menu, tearoff=0)
        self.font_menu.add_cascade(label="Size", menu=self.font_size_menu)
        self.font_size_menu.add_command(label="+", command=self.increase_font_size)
        self.font_size_menu.add_command(label="-", command=self.decrease_font_size)
        self.font_family_menu = tk.Menu(self.font_menu, tearoff=0)
        self.font_menu.add_cascade(label="Font Family", menu=self.font_family_menu)
        for font in self._available_fonts():
            text_widget = self.current_text_widget()
            self.font_family_menu.add_command(label=font,
                                              command=lambda font_name=font: self.set_font_name(text_widget, font_name),
                                              font=tkinter.font.Font(family=font)
                                              )

    def get_font(self, text_widget):
        """
        获取 Text 控件的字体样式
        :param text_widget: Text 控件
        :return: 字体样式
        """
        return text_widget.cget('font')

    def set_font_name(self, text_widget, font_name):
        """
        设置 Text 控件的字体名称
        :param event: 回调事件
        :param text_widget: Text 控件
        :param font_name: 字体名称
        :return: None
        """
        font_size = self._get_font_size()
        font_style = tkinter.font.Font(family=font_name, size=font_size)
        text_widget.config(font=font_style)
        self.tabs_mapping[self.current_tab()].text_area_font = font_style

    def _get_text_font(self, event=None):
        return self.tabs_mapping[self.current_tab()].text_area_font

    def _get_font_size(self, font=None):
        if font is None:
            font = self._get_text_font()
        return font.actual()["size"]

    def _get_font_name(self, font=None):
        if font is None:
            font = self._get_text_font()
        return font.actual()["family"]

    def increase_font_size(self, event=None):
        current_font = self._get_text_font()
        size = self._get_font_size(current_font)
        current_font.configure(size=size + 1)

    def decrease_font_size(self, event=None):
        current_font = self._get_text_font()
        size = self._get_font_size(current_font)
        if size > 1:  # Prevent setting font size to 0 or negative
            current_font.configure(size=size - 1)

    def _available_fonts(self):
        return tkinter.font.families(self.root)

    # 打开文件的函数
    def open_file(self):
        text_area, line_number_canvas, _ = self.new_file()
        # 打开一个文件对话框，让用户选择一个文件，并把文件的路径保存在self.file_path中
        file_path = filedialog.askopenfilename()
        # 打开用户选择的文件
        file = open(file_path, 'r')
        # 读取文件的内容
        content = file.read()
        # 把文件的内容插入到文本区域的第一行
        text_area.insert('1.0', content)
        # 更新行号
        self.update_line_numbers(None, line_number_canvas, text_area)
        # 关闭文件
        file.close()
        # 更新 文件名为打开的文件名
        current_tab = self.current_tab()
        self.update_tab_name(current_tab, file_path)
        self.tabs_mapping[current_tab].tab_file_path = file_path

    def new_file(self, event=None):
        # 在 notebook 中创建文本编辑器的 Text 部件
        text_frame = tk.Frame(self.notebook)
        text_frame.pack(fill=tk.BOTH, expand=1)

        # 在 Frame 中创建用于显示行号的 Text 部件
        line_number_canvas = tk.Text(text_frame, width=3, bg="yellow", state='disabled', takefocus=0)
        line_number_canvas.pack(side=tk.LEFT, fill=tk.Y)

        text_area = AutocompleteText(text_frame, undo=True)
        text_area.pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        status_bar = tk.Label(text_frame, text="", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        output_area = scrolledtext.ScrolledText(text_frame, height=10, state='normal')
        output_area.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

        self.notebook.add(text_frame, text='untitled')
        self.notebook.select(text_frame)

        text_area.bind("<Control-z>", self.undo)
        text_area.bind("<Control-y>", self.redo)
        text_area.bind("<Control-c>", self.copy)
        text_area.bind("<Control-v>", self.paste)
        text_area.bind("<Control-f>", self.display_find_box)
        # 然后，我们需要在文本区域每次更新时更新行号。这包括键盘输入和鼠标滚轮事件。
        text_area.bind("<Key>", lambda event: self.on_key_press(event, line_number_canvas, text_area, status_bar))
        text_area.bind("<MouseWheel>", lambda event: self.update_line_numbers(event, line_number_canvas, text_area))
        text_area.bind("<Tab>", self.handle_tab)

        text_area.focus_set()
        current_font = tkinter.font.nametofont(text_area.cget("font"))
        self.tabs_mapping[self.current_tab()] = Tab(text_frame, self.get_current_tab_path(),
                                                    text_area, current_font,
                                                    line_number_canvas, status_bar, output_area)
        return text_area, line_number_canvas, status_bar

    # 保存文件的函数
    def save_file(self, event=None, save_copy=False):
        current_tab = self.current_tab()
        cur_file_path = self.get_current_tab_path()
        if cur_file_path == "untitled" or save_copy:
            file_path = filedialog.asksaveasfilename()
        else:
            file_path = cur_file_path
        if file_path:
            file = open(file_path, 'w')
            text_widget = self.notebook.nametowidget(self.notebook.select()).winfo_children()[1]
            data = text_widget.get('1.0', 'end-1c')
            file.write(data)
            file.close()
            self.update_tab_name(current_tab, file_path)

    def close_file(self, event=None):
        current_tab = self.current_tab()
        text_widget = self.current_text_widget()
        data = text_widget.get('1.0', 'end-1c')
        cur_tab_path = self.get_current_tab_path()
        if cur_tab_path != "untitled":
            with open(cur_tab_path, "r") as fin:
                ori_data = fin.read()
                # 文件内容没有变化则可以直接关闭
                if data == ori_data:
                    self.close_tab(current_tab)
                    return

        if data:  # If there's data in the text widget
            choice = messagebox.askyesno("Save file", "Do you want to save the changes?")

            if choice:
                if cur_tab_path == 'untitled':
                    file_path = filedialog.asksaveasfilename()
                else:
                    file_path = cur_tab_path
                if not file_path:  # If the user didn't choose a new file path, use the existing one
                    file_path = cur_tab_path
                file = open(file_path, 'w')
                file.write(data)
                file.close()
                self.update_tab_name(current_tab, file_path)

        if self.notebook.index("end") == 1:  # If there is only one tab left, close the whole editor.
            self.root.destroy()
        else:
            self.close_tab(current_tab)

    def close_tab(self, tab):
        if tab in self.tabs_mapping:
            del self.tabs_mapping[tab]
        # 检查 tabs_mapping 是否需要更新
        # 比如原来有0,1,2,3,4 这5个tab,现在把2 close 掉了,那么小于2 的 tab 不受影响,大于 2 的 tab 需要序号减1
        tmp_tabs_mapping = {}
        for k, v in self.tabs_mapping.items():
            if k <= tab:
                tmp_tabs_mapping[k] = v
            else:
                tmp_tabs_mapping[k - 1] = v
        self.tabs_mapping = tmp_tabs_mapping
        self.notebook.forget(tab)

    def update_tab_name(self, tab, name):
        self.notebook.tab(tab, text=name)
        self.tabs_mapping[tab].tab_file_path = name

    def get_current_tab_path(self):
        current_tab = self.current_tab()
        return self.notebook.tab(current_tab, "text")

    def update_line_numbers(self, event, line_number_canvas, text_area):
        line_number_canvas.config(state='normal')
        line_number_canvas.delete('1.0', tk.END)  # 首先删除行号显示区的所有内容。
        # 索引字符串的格式是line.column，其中line是行号，column是列号
        number_of_lines = text_area.index('end - 1 chars').split('.')[0]  # 获取文本区域中的行数。
        line_numbers_string = "\n".join(
            str(no + 1) for no in range(int(number_of_lines)))  # 生成行号字符串，行号从1开始，每个行号之间用换行符隔开。
        line_number_canvas.insert('1.0', line_numbers_string)  # 将生成的行号字符串插入到行号显示区的开头。
        line_number_canvas.config(state='disabled')

    def undo(self, event=None):
        text_widget = self.current_text_widget()
        try:
            text_widget.edit_undo()
        except tk.TclError:
            pass

    def redo(self, event=None):
        text_widget = self.current_text_widget()
        try:
            text_widget.edit_redo()
        except tk.TclError:
            pass

    def copy(self, event=None):
        text_widget = self.current_text_widget()
        text_widget.event_generate("<<Copy>>")

    def paste(self, event=None):
        text_widget = self.current_text_widget()
        text_widget.event_generate("<<Paste>>")

    def find_first(self, text_area, find_input, tab, idx_start='1.0'):
        idx = text_area.search(find_input.get(), idx_start, stopindex=tk.END)
        if idx:
            text_area.tag_remove('found', '1.0', tk.END)
            text_area.tag_add('found', idx, f"{idx}+{len(find_input.get())}c")
            text_area.tag_config('found', foreground='red')
        tab.current_find_idx = idx  # Save the current find index
        tab.current_find_count = 1  # Add this line
        count = self.count_matches(text_area, find_input)
        tab.find_status_label.config(text=f"{tab.current_find_count} of {count} matched")
        return idx

    def find_next(self, text_area, find_input, tab):
        if tab.current_find_idx:  # If there's a previous find index, start from there
            idx = text_area.search(find_input.get(), f"{tab.current_find_idx}+{len(find_input.get())}c",
                                   stopindex=tk.END)
        else:  # Otherwise, start from the beginning
            idx = text_area.search(find_input.get(), '1.0', stopindex=tk.END)
        if idx:
            text_area.tag_remove('found', '1.0', tk.END)
            text_area.tag_add('found', idx, f"{idx}+{len(find_input.get())}c")
            text_area.tag_config('found', foreground='red')
        tab.current_find_idx = idx  # Save the current find index
        tab.current_find_count += 1  # Add this line
        count = self.count_matches(text_area, find_input)
        if tab.current_find_count > count:
            tab.current_find_count = 0
        tab.find_status_label.config(text=f"{tab.current_find_count} of {count} matched")
        return idx

    def find_prev(self, text_area, find_input, tab):
        find_text = find_input.get()
        if tab.current_find_idx:
            cursor_pos = text_area.index(tab.current_find_idx)
        else:
            cursor_pos = text_area.index(tk.INSERT)
        lines = text_area.get('1.0', cursor_pos).split('\n')
        line, col = map(int, cursor_pos.split('.'))
        while line > 0:
            current_line = lines[line - 1]
            if line != len(lines):
                current_line = current_line[:col]
            idx = current_line.rfind(find_text)
            if idx != -1:
                idx_str = f"{line}.{idx}"
                text_area.tag_remove('found', '1.0', tk.END)
                text_area.tag_add('found', idx_str, f"{idx_str}+{len(find_text)}c")
                text_area.tag_config('found', foreground='red')
                tab.current_find_idx = idx_str
                tab.current_find_count -= 1  # Add this line
                count = self.count_matches(text_area, find_input)
                if tab.current_find_count < 0:
                    tab.current_find_count = count
                tab.find_status_label.config(text=f"{tab.current_find_count} of {count} matched")
                return idx_str
            line -= 1
            col = len(lines[line - 1]) if line > 0 else 0
        return None

    def find_all(self, text_area, find_input, tab):
        text_area.tag_remove('found', '1.0', tk.END)
        idx_start = '1.0'
        while True:
            idx = text_area.search(find_input.get(), idx_start, stopindex=tk.END)
            if not idx:
                break
            text_area.tag_add('found', idx, f"{idx}+{len(find_input.get())}c")
            text_area.tag_config('found', foreground='red')
            idx_start = f"{idx}+{len(find_input.get())}c"
        count = self.count_matches(text_area, find_input)
        tab.find_status_label.config(text=f"all {count} matched")

    def count_matches(self, text_area, find_input):
        count = 0
        idx_start = '1.0'
        while True:
            idx = text_area.search(find_input.get(), idx_start, stopindex=tk.END)
            if not idx:
                break
            count += 1
            idx_start = f"{idx}+{len(find_input.get())}c"
        return count

    def display_find_box(self, event=None):
        find_window = tk.Toplevel(self.root)
        find_window.title(f"Find text of file:{self.get_current_tab_path()}")
        tab = self.tabs_mapping[self.current_tab()]
        find_window.transient(self.root)
        find_window.resizable(False, False)
        find_label = tk.Label(find_window, text="Find what:")
        find_label.pack(side=tk.LEFT)
        find_input = tk.Entry(find_window, width=30)
        find_input.pack(side=tk.LEFT, fill=tk.X, expand=1)
        find_status_label = tk.Label(find_window, text='', anchor='w')  # Add this line
        find_status_label.pack(side=tk.BOTTOM, fill=tk.X)  # Add this line
        tab.find_status_label = find_status_label
        find_button = tk.Button(find_window, text="Find",
                                command=lambda: self.find_first(self.current_text_widget(), find_input, tab))
        find_button.pack(side=tk.LEFT, padx=2)
        find_next_button = tk.Button(find_window, text="Find Next",
                                     command=lambda: self.find_next(self.current_text_widget(),
                                                                    find_input, tab))
        find_next_button.pack(side=tk.LEFT, padx=2)
        find_prev_button = tk.Button(find_window, text="Find Prev",
                                     command=lambda: self.find_prev(self.current_text_widget(),
                                                                    find_input, tab))
        find_prev_button.pack(side=tk.LEFT, padx=2)
        find_all_button = tk.Button(find_window, text="Find All",
                                    command=lambda: self.find_all(self.current_text_widget(), find_input, tab))
        find_all_button.pack(side=tk.LEFT, padx=2)
        find_window.protocol("WM_DELETE_WINDOW",
                             lambda: (find_window.destroy(), self.remove_highlights(self.current_text_widget()),
                                      self.reset_find_count()))

    def remove_highlights(self, text_area):
        text_area.tag_remove('found', '1.0', tk.END)

    def get_cursor_pos(self):
        text_widget = self.current_text_widget()
        pos = text_widget.index(tk.INSERT)
        return pos

    def display_cursor_pos(self, event, status_bar):
        pos = self.get_cursor_pos()
        line, col = pos.split('.')
        font_size = self._get_font_size()
        font_name = self._get_font_name()
        status_bar.config(text=f"Line {line}, Col {col} |  Font name:{font_name} | Font size:{font_size}")

    def on_key_press(self, event, line_number_canvas, text_area, status_bar):
        self.display_cursor_pos(event, status_bar)
        self.update_line_numbers(event, line_number_canvas, text_area)
        self.handle_brackets(event)
        self.handle_backspace(event)

    def on_closing(self):
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            self.root.destroy()

    def current_text_widget(self):
        text_widget = self.notebook.nametowidget(self.notebook.select()).winfo_children()[1]
        return text_widget

    def current_tab(self):
        return self.notebook.index(self.notebook.select())

    def reset_find_count(self):
        tab = self.tabs_mapping[self.current_tab()]
        tab.cur_match_cnt = 0
        tab.all_match_cnt = 0

    def select_all(self, event=None):
        """
        全选文本
        :param event:
        :return:
        """
        current_tab = self.tabs_mapping[self.current_tab()]
        text_area = current_tab.text_area
        text_area.tag_add(tk.SEL, "1.0", tk.END)
        return 'break'  # 阻止事件进一步传播

    def run_script(self, event=None):
        current_tab = self.tabs_mapping[self.current_tab()]
        script_path = current_tab.tab_file_path
        if script_path is not None and script_path.endswith('.py'):
            start_time = time.time()
            process = subprocess.Popen(['python', script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            end_time = time.time()
            elapsed_time = end_time - start_time
            current_tab.output_area.config(state='normal')
            current_tab.output_area.delete('1.0', tk.END)
            current_tab.output_area.insert(tk.END, stdout.decode())
            if stderr:
                current_tab.output_area.insert(tk.END, '\n' + stderr.decode())
            current_tab.output_area.insert(tk.END, f'\n[Finished in {elapsed_time * 1000:.2f} ms]')
            current_tab.output_area.config(state='disabled')

    import keyword

    def highlight_keywords(self, event=None):
        current_tab = self.tabs_mapping[self.current_tab()]
        text_area = current_tab.text_area

        # 创建一个新的 tag，并设置格式
        text_area.tag_configure("keyword", foreground="pink")

        # 对每个 Python 关键字进行高亮显示
        for word in _get_py_keywords():
            start_pos = '1.0'
            while True:
                start_pos = text_area.search(r'\m{}\M'.format(word), start_pos, 'end', regexp=True)
                if not start_pos:
                    break
                end_pos = f"{start_pos.split('.')[0]}.{int(start_pos.split('.')[1]) + len(word)}"
                text_area.tag_add("keyword", start_pos, end_pos)
                start_pos = end_pos

    def handle_tab(self, event=None):
        event.widget.insert(tk.INSERT, "    ")  # 插入四个空格
        return "break"  # 阻止默认的 Tab 行为

    def handle_brackets(self, event=None):
        """
        处理括号自动匹配
        :param event:
        :return:
        """
        char = event.char  # 获取输入的字符
        if char in ['(', '[', '{', '"', "'"]:  # 如果输入的字符是左括号或者单双引号
            event.widget.insert(tk.INSERT, {'(': ')', '[': ']', '{': '}', '"': '"', "'": "'"}[char])  # 插入配对的右括号
            event.widget.mark_set(tk.INSERT, f"{tk.INSERT} - 1 chars")  # 将光标移动到两个括号之间
            return "break"  # 阻止默认的字符插入行为

    def handle_backspace(self, event):
        """
        删除成对的括号、单双引号等
        :param event:
        :return:
        """
        text_area = event.widget
        index = text_area.index(tk.INSERT)
        line, col = map(int, index.split('.'))
        if col > 0:  # 检查是否在行的开始
            char_before = text_area.get(f"{line}.{col - 1}")  # 获取光标前的字符
            char_after = text_area.get(f"{line}.{col}")  # 获取光标后的字符
            if (char_before, char_after) in [('(', ')'), ('[', ']'), ('{', '}')]:  # 如果是配对的括号
                text_area.delete(f"{line}.{col}")  # 删除光标后的字符


# 创建一个Tk窗口对象
root = tk.Tk()
root.title("LyText")
root.state("zoomed")
default_font = tk.font.nametofont("TkDefaultFont")
default_font.configure(size=24)
# Apply the font to all Text widgets
root.option_add('*Text.font', default_font)
# 创建一个文本编辑器对象
te = TextEditor(root)
# 启动Tk的事件循环
root.mainloop()
