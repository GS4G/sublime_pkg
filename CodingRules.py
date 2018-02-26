"""
enyx_beauty for Sublime Text 3

This package attempts to recreate to some level of fidelity the features
in the vhdl-mode in Emacs.
"""
import os
import time
import re
import textwrap
import string
import sublime
import sublime_plugin

from . import vhdl_lang as vhdl
from . import vhdl_util as util

# Highlight matching regions.
class nx_lint_event(sublime_plugin.EventListener):

    def __init__(self):
        self.pending = 0

    def is_vhdl(self, view):
        
        if view.file_name() is not None:
            filename, file_extension = os.path.splitext(view.file_name())
            if file_extension == ".vhd":
                return True
            else:
                return False

    def on_load(self, view):
        s = sublime.load_settings("CodingRules.sublime-settings")
        lint_on_load = s.get("nx_lint_on_load", False)
        if self.is_vhdl(view) and lint_on_load:
            view.run_command("coding_linting")

    def on_activated(self, view): #similar to on_load
        s = sublime.load_settings("CodingRules.sublime-settings")
        lint_on_load = s.get("nx_lint_on_load", False)

        if self.is_vhdl(view) and lint_on_load:
            view.run_command("coding_linting")

    def on_pre_save(self, view):
        
        s = sublime.load_settings("CodingRules.sublime-settings")
        clean_on_save = s.get("nx_clean_space_tab_on_save", False)
        lint_on_save = s.get("nx_lint_on_save", False)

        if self.is_vhdl(view):
            if clean_on_save:
                print("save")
                view.run_command("auto_clean_space")
            if lint_on_save:
                view.run_command("coding_linting")

    def on_modified(self, view):
        s = sublime.load_settings("CodingRules.sublime-settings")
        delay = s.get("nx_lint_auto_lint_delay", 10000)
        auto_lint = s.get("nx_lint_auto_lint", False)

        if view.file_name() is not None:
            if auto_lint and self.is_vhdl(view):
                self.pending = self.pending + 1
                sublime.set_timeout(lambda: self.lint_time(view, auto_lint), delay)

    def lint_time(self, view, auto_lint):
        self.pending = self.pending - 1
        if self.pending > 0:
            return
        view.run_command("coding_linting")

# ----------------------------------------------------------------


class coding_linting(sublime_plugin.TextCommand):

    error_type_msg = ""

    def run(self, edit):
        self.error_type_msg = "Coding rules error:"
        # lint_array = ["decla","arch"]
        decla_work_array = ["constant", "variable", "signal", " type"]
        prefix_work_array = ["inst_", "p_", "g_", "b_"]
        self.erase_regions(decla_work_array)
        self.prefix_decla(decla_work_array)
        self.erase_regions(prefix_work_array)
        self.prefix_arch(prefix_work_array)
        sublime.status_message(self.error_type_msg)

    def erase_regions(self, region_key=[]):
        for region_to_del in region_key:
                try:
                    self.view.erase_regions(region_to_del)
                except AttributeError:
                    pass

    def lint_action(self, key, to_lint=[]):
        if to_lint:  # check if empty
            regex = "\W|\W".join(to_lint)
            regex = "\W" + regex + "\W"
            # print(regex+'\n')
            re_regions = self.view.find_all(regex)
            self.view.add_regions(key,
                                  re_regions,
                                  "invalid",
                                  "dot",
                                  sublime.DRAW_EMPTY)  # linting step

            self.error_type_msg += str(key + ", ")
            #print(key)

    def prefix_decla(self, work_array=[]):

        end_file = self.view.size() - 1
        whole_region = sublime.Region(0, end_file)
        # whole_region = self.view.visible_region()
        buffer_str = self.view.substr(whole_region)
        lines = buffer_str.split('\n')

        lists = {}
        lists_error = {}

        for region in work_array:
            lists[region] = []
            lists_error[region] = []

        # search constant/variable/signal declaration
        for i, line in enumerate(lines):  # search
            line_clean = line.split('--')[0]
            for region in work_array:
                try:
                    lists[region].append(re.search('\s*.' + region + '\s*(\w*)', line_clean).group(1))
                except AttributeError:
                    pass

        # search error in constant/variable/signal declaration
        for search_error in lists["constant"]:
            if not search_error.isupper():
                lists_error["constant"].append(search_error)

        for search_error in lists["variable"]:
            if not search_error.lower().startswith("v_"):
                lists_error["variable"].append(search_error)

        for search_error in lists["signal"]:
            if not search_error.lower().startswith(("rst",
                                                    "reset",
                                                    "clk",
                                                    "clock",
                                                    "r_",
                                                    "w_",
                                                    "i_")):
                lists_error["signal"].append(search_error)

        for search_error in lists[" type"]:
            if not search_error.lower().startswith(("t_")):
                lists_error[" type"].append(search_error)

        for region in work_array:
            if lists_error[region]:
                self.lint_action(region, lists_error[region])
                # print(region + str(lists_error[region])+"\n")

    def prefix_arch(self, work_array=[]):
        lists_error = {}

        for region in work_array:
            lists_error[region] = []

        end_file = self.view.size() - 1
        whole_region = sublime.Region(0, end_file)
        # whole_region = self.view.visible_region()
        buffer_str = self.view.substr(whole_region)
        lines = buffer_str.split('\n')

        for i, line in enumerate(lines):
            line_clean = line.split('--')[0]
            # inst_ search
            if (re.search(r'(generic|port)\s*map', line_clean, re.IGNORECASE)):
                if(lines[i - 1].find(":") != -1):
                    if (lines[i - 1].find("inst_") == -1):
                        split = re.findall(r"[\w']+", lines[i - 1])
                        lists_error["inst_"].append(split[0])

            # p_ process search
            if re.search(r'\Wprocess\W', line_clean, re.IGNORECASE) and not re.search(' p_', line_clean):
                if re.search(':', line_clean):  # case name exist
                    split = re.findall(r"[\w']+", lines[i])
                    lists_error["p_"].append(split[0])

            # b_ block search
            if re.search(':\s*block', line_clean, re.IGNORECASE) and not re.search(' b_', line_clean):
                if re.search(':', line_clean):  # case name exist
                    split = re.findall(r"[\w']+", lines[i])
                    lists_error["b_"].append(split[0])

            # g_ generate search
            if re.search('generate', line_clean, re.IGNORECASE) and not re.search(' g_', line_clean):
                if re.search(':', line_clean):  # case name exist
                    split = re.findall(r"[\w']+", lines[i])
                    lists_error["g_"].append(split[0])

        for region in work_array:
            self.lint_action(region, lists_error[region])
            # print(region + str(lists_error[region])+"\n")


class auto_clean_space(sublime_plugin.TextCommand):

    def run(self, edit):
        spurious_space_map_process = re.compile(r'(map|process)\s+\(')
        spurious_tabulation = re.compile(r'\t')
        spurious_end_space = re.compile(r'\s+$')
        spurious_comma_space = re.compile(r'\s+(;|,)')
        # Create points for a region that define beginning and end.
        begin = 0
        end = self.view.size()

        # Slurp up entire buffer
        whole_region = sublime.Region(begin, end)
        buffer_str = self.view.substr(whole_region)
        lines = buffer_str.split('\n')

        for i, line in enumerate(lines):
            correct = spurious_tabulation.sub(4 * ' ', line)
            correct = spurious_end_space.sub('', correct)
            correct = spurious_comma_space.sub(r'\1', correct)
            lines[i] = spurious_space_map_process.sub(r'\1(', correct)

        # Recombine into one big blobbed string.
        buffer_str = '\n'.join(lines)

        buffer_str = re.sub(r'\n\n\n+','\n\n', buffer_str)

        # Annnd if all went well, write it back into the buffer
        self.view.replace(edit, whole_region, buffer_str)


class beautify(sublime_plugin.TextCommand):
    def run(self, edit):
        # Save original point, and convert to row col.  Beautify
        # will change the number of characters in the file, so
        # need coordinates to know where to go back to.
        original_region = self.view.sel()[0]
        original_point = original_region.begin()
        orig_x, orig_y = self.view.rowcol(original_point)

        # Create points for a region that define beginning and end.
        begin = 0
        end = self.view.size() - 1

        # Slurp up entire buffer
        whole_region = sublime.Region(begin, end)
        buffer_str = self.view.substr(whole_region)
        lines = buffer_str.split('\n')

        # Get the scope for column 0 of each line.
        point = 0
        scope_list = []
        while not util.is_end_line(self, point):
            scope_list.append(self.view.scope_name(point))
            point = util.move_down(self, point)
        scope_list.append(self.view.scope_name(point))

        # Process each line
        # Left justify
        vhdl.left_justify(lines)

        # Because there are some really terrible typists out there
        # I end up having to MAKE SURE that symbols like : := <= and =>
        # have spaces to either side of them.  I'm just going to wholesale
        # replace them all with padded versions and then I remove extra space
        # later, which seems wasteful, but easier than trying to come up with
        # a ton of complicated patterns.
        vhdl.pad_vhdl_symbols(lines)

        # Remove extra blank space and convert tabs to spaces
        vhdl.remove_extra_space(lines)

        # Align
        vhdl.align_block_on_re(lines=lines,
                               regexp=r':(?!=)',
                               scope_data=scope_list)
        vhdl.align_block_on_re(lines=lines,
                               regexp=r':(?!=)\s?(?:in\b|out\b|inout\b|buffer\b)?\s*',
                               padside='post',
                               scope_data=scope_list)

        vhdl.align_block_on_re(lines=lines,
                               regexp=r'<|:(?==)',
                               scope_data=scope_list)

        vhdl.align_block_on_re(lines=lines,
                               regexp=r'=>',
                               scope_data=scope_list)

        # Indent!  Get some settings first.
        use_spaces = util.get_vhdl_setting(self, 'translate_tabs_to_spaces')
        tab_size = util.get_vhdl_setting(self, 'tab_size')
        #print('enyx_beauty: Indenting.')
        vhdl.indent_vhdl(lines=lines, initial=0, tab_size=tab_size,
                         use_spaces=use_spaces)

        # Post indent alignment
        vhdl.align_block_on_re(lines=lines,
                               regexp=r'\bwhen\b',
                               scope_data=scope_list)

        # Recombine into one big blobbed string.
        buffer_str = '\n'.join(lines)

        # And if all went well, write it back into the buffer
        self.view.replace(edit, whole_region, buffer_str)

        # Put cursor back to original point (roughly)
        original_point = self.view.text_point(orig_x, orig_y)
        util.set_cursor(self, original_point)

# ----------------------------------------------------------------


