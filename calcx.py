import tkinter as tk
from tkinter import messagebox, colorchooser, font as tkFont, OptionMenu, Scale
from threading import Thread, Event
import time
import re
import logging
import math # Standard math for expression evaluation
import cmath # For complex number functions if explicitly named
import json
import os
from collections import deque
import datetime

# Optional libraries
try:
    import pyperclip
except ImportError:
    pyperclip = None
    try:
        root_check = tk.Tk()
        root_check.withdraw()
        messagebox.showerror("Dependency Error", "Pyperclip library not found. Please install it: pip install pyperclip")
        root_check.destroy()
    except tk.TclError:
        print("Pyperclip library not found and Tkinter is not available to show a graphical error.")
        print("Please install it: pip install pyperclip")
    exit()

# Pint (Unit Conversion) is removed.

try:
    from dateutil import parser as dateutil_parser
    from dateutil.relativedelta import relativedelta
except ImportError:
    dateutil_parser = None
    relativedelta = None

try:
    import statistics
except ImportError:
    statistics = None

# Sympy will be imported dynamically when needed for equation solving.

class ClipboardCalculator:
    def __init__(self):
        # For detailed debugging, change level to logging.DEBUG
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s')
        self.logger = logging.getLogger(__name__)

        self.root = tk.Tk()
        self.root.withdraw()

        if not dateutil_parser:
            self.logger.warning("python-dateutil library not found. Advanced date parsing will be unavailable. (pip install python-dateutil)")
        if not statistics:
            self.logger.warning("statistics library not found. Statistical functions will be unavailable. (pip install statistics)")

        self.settings_file = "CalcX_settings.json"
        self.settings = self.load_settings()
        self.themes = {
            "Light": {"bg": "#F0F0F0", "text": "black", "button_bg": "#E0E0E0", "button_active_bg": "#C0C0C0"},
            "Dark": {"bg": "#2E2E2E", "text": "white", "button_bg": "#3E3E3E", "button_active_bg": "#505050"},
            "Yellowish": {"bg": "lightyellow", "text": "black", "button_bg": "#FFFACD", "button_active_bg": "khaki"}
        }
        self.apply_theme(self.settings.get("theme_name", "Yellowish"), from_load=True)

        self.last_clip = ""
        self.stop_event = Event()
        self.monitoring_paused = False
        self.calculation_history = deque(maxlen=self.settings.get("max_history_items", 20))
        self.x_offset = 0
        self.y_offset = 0
        self.sympy_notified = False
        self.dateutil_notified = not dateutil_parser
        self.stats_notified = not statistics
        self._last_sympy_solution_obj = None

        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes('-topmost', self.settings.get("always_on_top", True))
        self.overlay.overrideredirect(True)
        self.overlay.attributes('-alpha', self.settings.get("overlay_opacity", 1.0))
        overlay_geom = self.settings.get("overlay_geometry", "+50+50")
        self.overlay.geometry(overlay_geom)
        self.overlay.configure(bg=self.settings.get("overlay_bg_color", 'lightyellow'))

        self.status_var = tk.StringVar()
        self.status_var.set("Ready...")
        self.result_label = tk.Label(
            self.overlay, textvariable=self.status_var,
            font=(self.settings.get("font_family", "Arial"), self.settings.get("font_size", 12)),
            bg=self.settings.get("overlay_bg_color", 'lightyellow'),
            fg=self.settings.get("overlay_text_color", 'black'),
            padx=10, pady=5
        )
        self.result_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.button_frame = tk.Frame(self.overlay, bg=self.settings.get("overlay_bg_color", 'lightyellow'))
        self.button_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.update_overlay_buttons_appearance()

        self.result_label.bind("<ButtonPress-1>", self.start_move)
        self.result_label.bind("<ButtonRelease-1>", self.stop_move)
        self.result_label.bind("<B1-Motion>", self.on_move)
        self.overlay.bind("<ButtonPress-1>", self.start_move)
        self.overlay.bind("<ButtonRelease-1>", self.stop_move)
        self.overlay.bind("<B1-Motion>", self.on_move)

        if pyperclip:
            self.monitor_thread = Thread(target=self.monitor_clipboard)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
        else:
            self.status_var.set("Error: Pyperclip not found!")
            self.logger.error("Pyperclip not found, clipboard monitoring disabled.")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.update_overlay_appearance()
        self.root.after(30000, self.save_overlay_geometry_periodically)

    def update_overlay_buttons_appearance(self):
        for widget in self.button_frame.winfo_children():
            widget.destroy()
        common_button_options = {
            "bg": self.settings.get("overlay_button_bg_color", self.settings.get("overlay_bg_color", 'lightyellow')),
            "activebackground": self.settings.get("overlay_button_active_bg_color", "lightgrey"),
            "bd": 0, "font": (self.settings.get("font_family", "Arial"), 8),
            "padx": 2, "pady": 0
        }
        pause_text, pause_fg = ("►", 'green') if self.monitoring_paused else ("❚❚", 'blue')
        self.pause_resume_btn = tk.Button(self.button_frame, text=pause_text, command=self.toggle_pause_monitoring, fg=pause_fg, **common_button_options)
        self.pause_resume_btn.pack(side=tk.TOP, anchor=tk.NE)
        self.history_btn = tk.Button(self.button_frame, text="H", command=self.show_history_window, fg='green', **common_button_options)
        self.history_btn.pack(side=tk.TOP, anchor=tk.NE)
        self.settings_btn = tk.Button(self.button_frame, text="S", command=self.show_settings_window, fg='purple', **common_button_options)
        self.settings_btn.pack(side=tk.TOP, anchor=tk.NE)
        self.close_btn = tk.Button(self.button_frame, text="X", command=self.on_close, fg='red', **common_button_options)
        self.close_btn.pack(side=tk.TOP, anchor=tk.NE)

    def save_settings(self):
        try:
            if hasattr(self, 'overlay') and self.overlay.winfo_exists():
                self.settings["overlay_geometry"] = self.overlay.geometry()
            else:
                self.settings.setdefault("overlay_geometry", "+50+50")
            self.settings["max_history_items"] = self.calculation_history.maxlen
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
            self.logger.info(f"Settings saved to {self.settings_file}")
        except Exception as e:
            self.logger.error(f"Error saving settings: {e}")

    def load_settings(self):
        defaults = {
            "font_family": "Arial", "font_size": 12,
            "overlay_bg_color": "lightyellow", "overlay_text_color": "black",
            "overlay_button_bg_color": "lightyellow", "overlay_button_active_bg_color": "lightgrey",
            "always_on_top": True, "auto_copy_result": False,
            "monitoring_interval_ms": 500, "max_history_items": 20,
            "overlay_geometry": "+50+50", "overlay_opacity": 1.0, "theme_name": "Yellowish"
        }
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f: loaded_settings = json.load(f)
                for key, value in defaults.items():
                    if key not in loaded_settings: loaded_settings[key] = value
                self.logger.info(f"Settings loaded from {self.settings_file}")
                return loaded_settings
            return defaults
        except Exception as e:
            self.logger.error(f"Error loading settings, using defaults: {e}")
            return defaults
            
    def apply_theme(self, theme_name, from_load=False):
        theme_colors = self.themes.get(theme_name)
        if theme_colors:
            self.settings["overlay_bg_color"] = theme_colors["bg"]
            self.settings["overlay_text_color"] = theme_colors["text"]
            self.settings["overlay_button_bg_color"] = theme_colors.get("button_bg", theme_colors["bg"])
            self.settings["overlay_button_active_bg_color"] = theme_colors.get("button_active_bg", "lightgrey")
            self.settings["theme_name"] = theme_name
            if not from_load:
                self.update_overlay_appearance()
                self.save_settings()
        elif not from_load:
             self.logger.warning(f"Theme '{theme_name}' not found.")

    def update_overlay_appearance(self):
        font = (self.settings.get("font_family", "Arial"), self.settings.get("font_size", 12))
        bg_color = self.settings.get("overlay_bg_color", 'lightyellow')
        fg_color = self.settings.get("overlay_text_color", 'black')
        opacity = self.settings.get("overlay_opacity", 1.0)
        if hasattr(self, 'overlay') and self.overlay.winfo_exists():
            self.overlay.configure(bg=bg_color)
            self.overlay.attributes('-alpha', opacity)
            self.result_label.configure(font=font, bg=bg_color, fg=fg_color)
            self.button_frame.configure(bg=bg_color)
            self.update_overlay_buttons_appearance()
            self.overlay.attributes('-topmost', self.settings.get("always_on_top", True))
        if self.calculation_history.maxlen != self.settings.get("max_history_items", 20):
             self.calculation_history = deque(self.calculation_history, maxlen=self.settings.get("max_history_items", 20))
        self.auto_resize_overlay()

    def start_move(self, event): self.x_offset, self.y_offset = event.x, event.y
    def stop_move(self, event):
        self.x_offset, self.y_offset = None, None
        if hasattr(self, 'overlay') and self.overlay.winfo_exists():
            self.settings["overlay_geometry"] = self.overlay.geometry()
            self.save_settings()
    def on_move(self, event):
        if self.x_offset is not None and self.y_offset is not None:
            deltax, deltay = event.x - self.x_offset, event.y - self.y_offset
            x, y = self.overlay.winfo_x() + deltax, self.overlay.winfo_y() + deltay
            self.overlay.geometry(f"+{x}+{y}")

    def save_overlay_geometry_periodically(self):
        if not self.stop_event.is_set():
            if hasattr(self, 'overlay') and self.overlay.winfo_exists():
                current_geometry = self.overlay.geometry()
                if self.settings.get("overlay_geometry") != current_geometry:
                    self.settings["overlay_geometry"] = current_geometry
                    self.save_settings()
            self.root.after(30000, self.save_overlay_geometry_periodically)

    def monitor_clipboard(self):
        self.logger.info("Clipboard monitoring started.")
        while not self.stop_event.is_set():
            if self.monitoring_paused: time.sleep(0.1); continue
            try:
                cliptext_raw = pyperclip.paste()
                cliptext = "" if cliptext_raw is None else cliptext_raw.strip()
                if cliptext != self.last_clip:
                    self.last_clip = cliptext
                    self.logger.debug(f"Clipboard content: '{cliptext}'")
                    if self.looks_like_math_or_query(cliptext):
                        self.logger.info(f"Potential query detected: '{cliptext}'")
                        eval_result = self.safe_eval_router(cliptext)
                        if eval_result is not None:
                            is_error = isinstance(eval_result, str) and eval_result.startswith("Error:")
                            is_info = isinstance(eval_result, str) and eval_result.startswith("Info:")
                            is_complex_type = isinstance(eval_result, str) and ( 
                                eval_result.startswith("x =") or "->" in eval_result or "days" in eval_result.lower() or
                                re.match(r"\d{4}-\d{2}-\d{2}", eval_result) is not None or 
                                re.match(r"(0x[0-9a-fA-F]+|0b[01]+|0o[0-7]+)", eval_result, re.IGNORECASE) is not None 
                            )
                            if is_error or is_info:
                                self.root.after(0, self.update_result_display, cliptext, eval_result, True)
                            elif is_complex_type:
                                self.root.after(0, self.update_result_display, cliptext, eval_result, False, True)
                                self.add_to_history(cliptext, eval_result)
                                if self.settings.get("auto_copy_result", False) and pyperclip: pyperclip.copy(str(eval_result))
                            else: 
                                self.root.after(0, self.update_result_display, cliptext, eval_result)
                                self.add_to_history(cliptext, eval_result)
                                if self.settings.get("auto_copy_result", False) and pyperclip: pyperclip.copy(str(eval_result))
            except pyperclip.PyperclipException as e:
                self.logger.error(f"Pyperclip error: {e}. Clipboard access might be unavailable.")
                self.root.after(0, self.update_result_display, "Error", "Clipboard access issue.", True)
                time.sleep(5)
            except Exception as e:
                self.logger.error(f"Error in monitor_clipboard: {e}", exc_info=True)
                self.root.after(0, self.update_result_display, "Error", "Internal error.", True)
                time.sleep(1)
            time.sleep(self.settings.get("monitoring_interval_ms", 500) / 1000.0)
        self.logger.info("Clipboard monitoring stopped.")

    def looks_like_math_or_query(self, text):
        if not text or len(text) > 250: return False
        query_pattern = r'^[a-zA-Z0-9\s\.,\+\-\*/%^=√°\(\)\[\]\{\}:_]+$' 
        if not re.match(query_pattern, text):
            self.logger.debug(f"'{text}' did not match basic query pattern.")
            return False
        
        text_lower = text.lower()
        has_digits = any(char.isdigit() for char in text)
        
        special_keywords = [
            'sqrt', 'log', 'ln', 'sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'pi', 'e', 
            'abs', 'factorial', 'rad', 'deg', 'pow', 'of',
            'today', 'days', 'weeks', 'months', 'years', 'between', 'now', 'yesterday', 
            'tomorrow', 'ago', 'hence',
            'mean', 'median', 'mode', 'stdev', 'std', 'variance', 'avg',
            'hex', 'bin', 'oct', 'dec' 
        ]
        
        has_operator_char = any(op in text for op in '+-*/%^=√')
        has_special_keyword = any(re.search(r'\b' + re.escape(kw) + r'\b', text_lower) for kw in special_keywords)

        if has_digits or has_operator_char or has_special_keyword or 'x' in text_lower:
            self.logger.debug(f"'{text}' seems like a potential math/query.")
            return True
            
        self.logger.debug(f"'{text}' doesn't strongly resemble a math expression or query.")
        return False

    def _format_sympy_solution(self, solution_expr):
        try:
            import sympy
            val = float(solution_expr.evalf(n=15)) if isinstance(solution_expr, sympy.Expr) else float(solution_expr)
            if val == int(val): return str(int(val))
            for i in range(1, 7): 
                if abs(val - round(val, i)) < 1e-9: return f"{round(val, i):.10g}".rstrip('0').rstrip('.')
            return f"{val:.10g}".rstrip('0').rstrip('.') if abs(val) > 1e-7 and abs(val) < 1e7 else f"{val:.6e}"
        except: return str(solution_expr)

    def safe_eval_router(self, expr_str_input_orig: str):
        expr_str = expr_str_input_orig.strip()
        expr_lower = expr_str.lower()
        self.logger.debug(f"Routing: '{expr_str}'")

        # 1. Equation Solving
        if '=' in expr_str and 'x' in expr_lower:
            self.logger.debug("Attempting equation handler.")
            return self._handle_equation_solving(expr_str)

        # 2. Base Conversions
        base_keywords_check = ['hex', 'bin', 'oct', 'dec']
        # Check for patterns like "hex(...)", "0x...", or "... bin to dec"
        if any(expr_lower.startswith(kw + "(") for kw in base_keywords_check) or \
           re.search(r"\b(0x[0-9a-fA-F]+|0b[01]+|0o[0-7]+)\b", expr_str) or \
           ("to" in expr_lower and any(re.search(r'\b' + kw + r'\b', expr_lower) for kw in base_keywords_check)):
            self.logger.debug("Attempting base conversion handler.")
            return self._handle_base_conversion(expr_str)
        
        # 3. Date Calculations
        date_keywords_check = ['today', 'now', 'yesterday', 'tomorrow', 'days', 'weeks', 'months', 'years', 'between', 'ago', 'hence']
        if any(re.search(r'\b' + kw + r'\b', expr_lower) for kw in date_keywords_check) or \
           re.search(r'\d{4}-\d{2}-\d{2}', expr_str) or re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', expr_str):
            if dateutil_parser:
                self.logger.debug("Attempting date calculation handler.")
                return self._handle_date_calculation(expr_str)
            elif not self.dateutil_notified: self.dateutil_notified = True; return "Info: python-dateutil needed for date calculations."
            else: return "Error: python-dateutil not available."

        # 4. Currency Conversion (placeholder) - Keep this low priority
        if re.search(r"\d+\s*[A-Z]{3}\s*(?:to|in)\s*[A-Z]{3}", expr_str, re.IGNORECASE): # "to" or "in"
            return "Info: Currency conversion via API is planned."

        # 5. Statistical functions
        stat_keywords_check = ['mean', 'median', 'mode', 'stdev', 'std', 'variance', 'avg']
        if any(expr_lower.startswith(kw + "(") or expr_lower.startswith(kw + " ") for kw in stat_keywords_check):
            if statistics:
                self.logger.debug("Attempting stats handler.")
                return self._handle_statistical_calculation(expr_str)
            elif not self.stats_notified: self.stats_notified = True; return "Info: statistics module needed."
            else: return "Error: statistics module not available."

        self.logger.debug(f"Attempting standard expression handler as fallback for: '{expr_str}'")
        expr_sqrt_processed = re.sub(r'√\s*(\([^)]+\)|[a-zA-Z_0-9.]+)', r'sqrt(\1)', expr_str)
        return self._evaluate_standard_expression(expr_sqrt_processed)

    def _handle_equation_solving(self, expr_str):
        self.logger.debug(f"Equation handler received: '{expr_str}'")
        try:
            import sympy
            expr_for_sympy = expr_str.lower()
            expr_for_sympy = re.sub(r'√\s*(\([^)]+\)|[a-zA-Z_0-9.x]+)', r'sqrt(\1)', expr_for_sympy)
            expr_for_sympy = expr_for_sympy.replace('^', '**')
            lhs_str, rhs_str = expr_for_sympy.split('=', 1) 
            x_sym = sympy.symbols('x')
            sympy_context = {'x': x_sym, 'pi': sympy.pi, 'e': sympy.E, 'sqrt': sympy.sqrt, 'log': sympy.log, 'ln': sympy.log, 
                             'sin': sympy.sin, 'cos': sympy.cos, 'tan': sympy.tan, 'asin': sympy.asin, 'acos': sympy.acos, 
                             'atan': sympy.atan, 'abs': sympy.Abs, 'factorial': sympy.factorial, 'pow': sympy.Pow,
                             'rad': lambda dv: sympy.sympify(dv) * sympy.pi / 180, 'deg': lambda rv: sympy.sympify(rv) * 180 / sympy.pi}
            from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application
            transformations = standard_transformations + (implicit_multiplication_application,)
            lhs = parse_expr(lhs_str.strip(), local_dict=sympy_context, transformations=transformations)
            rhs = parse_expr(rhs_str.strip(), local_dict=sympy_context, transformations=transformations)
            solutions = sympy.solve(sympy.Eq(lhs, rhs), x_sym)
            if solutions: self._last_sympy_solution_obj = solutions[0]; return f"x = {self._format_sympy_solution(solutions[0])}"
            else: self._last_sympy_solution_obj = None; return "Error: No solution found"
        except ImportError:
            self._last_sympy_solution_obj = None
            if not self.sympy_notified: self.sympy_notified = True; return "Error: Sympy needed for equations (pip install sympy)"
            return "Error: Sympy not available" 
        except (SyntaxError, TypeError, sympy.SympifyError) as e:
            self._last_sympy_solution_obj = None; self.logger.error(f"Sympy parsing error for '{expr_str}': {e}"); return f"Error: Invalid equation syntax ({type(e).__name__})"
        except Exception as e:
            self._last_sympy_solution_obj = None; self.logger.error(f"Sympy error solving '{expr_str}': {e}", exc_info=True); return f"Error: Equation solving failed ({type(e).__name__})"

    def _handle_date_calculation(self, expr_str_orig):
        self.logger.debug(f"Date handler received: '{expr_str_orig}'")
        if not dateutil_parser or not relativedelta: 
            if not self.dateutil_notified: self.dateutil_notified = True; return "Info: python-dateutil needed."
            return "Error: python-dateutil not available"
        
        expr_work = expr_str_orig.strip()
        now = datetime.datetime.now()
        original_input_lower = expr_str_orig.lower().strip() 
        expr_work_substituted = expr_work # Start with original for substitutions

        # Perform keyword substitutions
        subs = {
            r"\btoday\b": now.strftime('%Y-%m-%d'),
            r"\byesterday\b": (now - datetime.timedelta(days=1)).strftime('%Y-%m-%d'),
            r"\btomorrow\b": (now + datetime.timedelta(days=1)).strftime('%Y-%m-%d'),
            r"\bnow\b": now.strftime('%Y-%m-%d %H:%M:%S')
        }
        for pattern, replacement in subs.items():
            expr_work_substituted = re.sub(pattern, replacement, expr_work_substituted, flags=re.IGNORECASE)
        
        self.logger.debug(f"Date expr after keyword sub: '{expr_work_substituted}'")

        # If original was just a keyword, parse the substituted string and format
        if original_input_lower in ['today', 'now', 'yesterday', 'tomorrow']:
            try:
                parsed_date = dateutil_parser.parse(expr_work_substituted.strip())
                return f"Parsed as: {parsed_date.strftime('%A, %B %d, %Y')}"
            except (dateutil_parser.ParserError, ValueError):
                return "Error: Could not parse substituted date keyword" # Should not happen if sub is correct

        try:
            # Pattern: date +/- N unit
            match_delta = re.match(r"(.+?)\s*([+-])\s*(\d+)\s*(days?|d|weeks?|wk|w|months?|mon|mo|years?|yr|y)\b", expr_work_substituted, re.IGNORECASE)
            if match_delta:
                date_part_str, op, num_str, unit = match_delta.groups(); num = int(num_str)
                base_date = dateutil_parser.parse(date_part_str.strip())
                delta = None
                if unit.startswith('d'): delta = relativedelta(days=num)
                elif unit.startswith('w'): delta = relativedelta(weeks=num)
                elif unit.startswith('mo'): delta = relativedelta(months=num)
                elif unit.startswith('y'): delta = relativedelta(years=num)
                if delta: return (base_date + delta if op == '+' else base_date - delta).strftime("%Y-%m-%d")

            # Pattern: N unit ago/hence
            match_ago_hence = re.match(r"(\d+)\s*(days?|weeks?|months?|years?)\s*(ago|hence|from now|earlier|later)\b", expr_work_substituted, re.IGNORECASE)
            if match_ago_hence:
                num_str, unit, direction = match_ago_hence.groups(); num = int(num_str)
                # Base date for "ago/hence" is assumed to be 'now' if not preceded by another date.
                # Here, 'now' would have been substituted already.
                base_date_str_for_ago_op = expr_work_substituted.split(match_ago_hence.group(0))[0].strip()
                base_date = dateutil_parser.parse(base_date_str_for_ago_op) if base_date_str_for_ago_op else now
                
                delta = None
                if unit.startswith('d'): delta = relativedelta(days=num)
                elif unit.startswith('w'): delta = relativedelta(weeks=num)
                elif unit.startswith('mo'): delta = relativedelta(months=num)
                elif unit.startswith('y'): delta = relativedelta(years=num)
                if delta: return (base_date - delta if direction in ['ago','earlier'] else base_date + delta).strftime("%Y-%m-%d")
            
            # Pattern: days between date1 and date2
            if "between" in expr_work_substituted.lower() and "and" in expr_work_substituted.lower():
                parts_between = re.split(r'\s+between\s+', expr_work_substituted, maxsplit=1, flags=re.IGNORECASE)
                if len(parts_between) == 2:
                    parts_and = re.split(r'\s+and\s+', parts_between[1], maxsplit=1, flags=re.IGNORECASE)
                    if len(parts_and) == 2:
                        try:
                            d1 = dateutil_parser.parse(parts_and[0].strip()).date()
                            d2 = dateutil_parser.parse(parts_and[1].strip()).date()
                            return f"{abs((d2 - d1).days)} days"
                        except (dateutil_parser.ParserError, ValueError) as e_parse: self.logger.debug(f"Date 'between' parse failed: {e_parse}")
            
            # Pattern: date1 - date2 (subtraction)
            sub_match = re.fullmatch(r"(.+?)\s*-\s*(.+)", expr_work_substituted.strip()) 
            if sub_match:
                d_str1, d_str2 = sub_match.groups()
                try:
                    dt1 = dateutil_parser.parse(d_str1.strip()); dt2 = dateutil_parser.parse(d_str2.strip())
                    is_date_only_str1 = not any(c in d_str1.lower() for c in [':', 'h', 'm', 's', 'am', 'pm'])
                    is_date_only_str2 = not any(c in d_str2.lower() for c in [':', 'h', 'm', 's', 'am', 'pm'])
                    if is_date_only_str1 and is_date_only_str2:
                        return f"{(dt1.date() - dt2.date()).days} days"
                    return str(dt1 - dt2) 
                except (dateutil_parser.ParserError, ValueError) as e_parse: self.logger.debug(f"Date subtraction parse failed: {e_parse}")

            # Fallback for parsing a single date string if no operations matched and original wasn't just a keyword
            if not (match_delta or match_ago_hence or sub_match or "between" in original_input_lower or \
                    original_input_lower in ['today', 'now', 'yesterday', 'tomorrow']): # Avoid re-parsing keywords
                try:
                    parsed_date = dateutil_parser.parse(expr_str_orig.strip()) # Try original string
                    return f"Parsed as: {parsed_date.strftime('%A, %B %d, %Y')}"
                except (dateutil_parser.ParserError, ValueError): pass
            
            return "Error: Date expression not recognized"
        except (dateutil_parser.ParserError, ValueError) as e: return f"Error: Invalid date format or operation"
        except Exception as e: self.logger.error(f"Date calc error for '{expr_str_orig}': {e}", exc_info=True); return f"Error: Date calculation failed ({type(e).__name__})"

    def _handle_base_conversion(self, expr_str):
        self.logger.debug(f"Base handler received: '{expr_str}'")
        expr_work = expr_str.lower().strip()
        try:
            m_func = re.match(r"(hex|bin|oct)\s*\((.+)\)", expr_work)
            if m_func:
                func, val_str = m_func.groups(); val_str = val_str.strip()
                base = 16 if val_str.startswith("0x") else 2 if val_str.startswith("0b") else 8 if val_str.startswith("0o") else 10
                num = int(val_str, base)
                if func == "hex": return hex(num)
                if func == "bin": return bin(num)
                if func == "oct": return oct(num)
            
            m_to = re.match(r"(.+?)\s+(?:(bin|hex|oct|dec)\s+)?to\s+(bin|hex|oct|dec)\b", expr_work)
            if m_to:
                val_str, base_from_kw, base_to_kw = m_to.groups(); val_str = val_str.strip()
                base_from = 10
                if base_from_kw: base_from = {'hex':16, 'bin':2, 'oct':8, 'dec':10}.get(base_from_kw, 10)
                else: base_from = 16 if val_str.startswith("0x") else 2 if val_str.startswith("0b") else 8 if val_str.startswith("0o") else 10
                num = int(val_str, base_from)
                if base_to_kw == "hex": return hex(num)
                if base_to_kw == "bin": return bin(num)
                if base_to_kw == "oct": return oct(num)
                if base_to_kw == "dec": return str(num)

            if re.fullmatch(r"0x[0-9a-f]+", expr_work, re.IGNORECASE): return f"{int(expr_work, 16)} (decimal)"
            if re.fullmatch(r"0b[01]+", expr_work, re.IGNORECASE): return f"{int(expr_work, 2)} (decimal)"
            if re.fullmatch(r"0o[0-7]+", expr_work, re.IGNORECASE): return f"{int(expr_work, 8)} (decimal)"
            
            return "Error: Base conversion format not recognized"
        except ValueError: return "Error: Invalid number for base conversion"
        except Exception as e: self.logger.error(f"Base conv error '{expr_str}': {e}", exc_info=True); return f"Error: Base conversion failed ({type(e).__name__})"

    def _handle_statistical_calculation(self, expr_str):
        self.logger.debug(f"Stats handler received: '{expr_str}'")
        if not statistics:
            if not self.stats_notified: self.stats_notified = True; return "Info: statistics module needed."
            return "Error: statistics module not available"
        expr_lower = expr_str.lower().strip()
        m = re.match(r"(mean|median|mode|stdev|std|variance|avg)\s*\(?([^)]*)\)?", expr_lower)
        if m:
            func, data_s = m.groups(); data_s = data_s.strip()
            try:
                nums_s = re.split(r'[\s,;]+', data_s); nums = [float(n) for n in nums_s if n]
                if not nums: return "Error: No data for statistics"
                res = None
                if func in ["mean","avg"]: res = statistics.mean(nums)
                elif func == "median": res = statistics.median(nums)
                elif func == "mode": 
                    try: res = statistics.mode(nums)
                    except statistics.StatisticsError: return "Error: No unique mode or multimodal data"
                elif func in ["stdev","std"]: 
                    if len(nums) < 2: return "Error: Stdev requires at least 2 data points"
                    res = statistics.stdev(nums)
                elif func == "variance":
                    if len(nums) < 2: return "Error: Variance requires at least 2 data points"
                    res = statistics.variance(nums)
                if res is not None: return int(res) if res == int(res) else round(res, 6)
            except ValueError: return "Error: Invalid data for statistics (non-numeric)"
            except Exception as e: self.logger.error(f"Stats error '{expr_str}': {e}", exc_info=True); return f"Error: Stats failed ({type(e).__name__})"
        return "Error: Statistical function not recognized"

    def _evaluate_standard_expression(self, expr_str_input):
        self.logger.debug(f"Standard eval received: '{expr_str_input}'")
        # Start with the original string, strip whitespace
        expr_proc = expr_str_input.strip()
        
        # Store a version for lowercase keyword matching, but try to use original case in replacements where possible
        expr_lower_for_keywords = expr_proc.lower()

        # Percentage processing
        # More robust regex for X% of Y, allows X and Y to be numbers or parenthesized expressions
        # ((?:\([^)]+\)|(?:\d+\.?\d*|\.\d+))) matches (expr) or number
        percent_of_pattern = r'((?:\([^)]+\)|(?:\d+\.?\d*|\.\d+)))\s*%\s*of\s*((?:\([^)]+\)|(?:\d+\.?\d*|\.\d+)))'
        expr_proc = re.sub(percent_of_pattern, r'((\1)/100)*(\2)', expr_proc, flags=re.IGNORECASE) # ignore case for "of"

        # Standalone X%
        # ((?:\([^)]+\)|(?:\d+\.?\d*|\.\d+))) matches (expr) or number
        # (?<![a-zA-Z_0-9\.]) ensures not part of a variable name
        standalone_percent_pattern = r'(?<![a-zA-Z_0-9\.])((?:\([^)]+\)|(?:\d+\.?\d*|\.\d+)))\s*%'
        expr_proc = re.sub(standalone_percent_pattern, r'((\1)/100)', expr_proc)
        
        # Now, convert to lower for general operator and function name consistency for eval
        expr_proc_eval = expr_proc.lower()
        
        expr_proc_eval = expr_proc_eval.replace(',', '') 
        expr_proc_eval = expr_proc_eval.replace('×', '*').replace('÷', '/')
        expr_proc_eval = expr_proc_eval.replace('^', '**')
        
        # Careful 'x' to '*' replacement, avoid affecting hex numbers or function names
        # Replace 'x' if it's between digits/parens, or a digit/paren and a space, or space and digit/paren
        expr_proc_eval = re.sub(r'(?<=[0-9\)\s])\s*x\s*(?=[\s0-9\(a-z_])', '*', expr_proc_eval)


        allowed_names = {"pi": math.pi, "e": math.e, "abs": math.fabs, "factorial": math.factorial, "gamma": math.gamma, 
                         "lgamma": math.lgamma, "sqrt": math.sqrt, "cbrt": math.cbrt, "exp": math.exp, "expm1": math.expm1,
                         "log": math.log, "log10": math.log10, "log2": math.log2, "log1p": math.log1p,
                         "sin": math.sin, "cos": math.cos, "tan": math.tan, "asin": math.asin, "acos": math.acos, 
                         "atan": math.atan, "atan2": math.atan2, "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
                         "asinh": math.asinh, "acosh": math.acosh, "atanh": math.atanh,
                         "rad": math.radians, "deg": math.degrees, "pow": pow, 
                         "hypot": math.hypot, "floor": math.floor, "ceil": math.ceil, "trunc": math.trunc,
                         "modf": math.modf, "erf": math.erf, "erfc": math.erfc, "gcd": math.gcd}
        if hasattr(math, 'lcm'): allowed_names["lcm"] = math.lcm

        char_val_pattern = r'^[0-9a-z\s_().+\-*/%^**j]+$' # Allows %, round uses built-in
        if not re.match(char_val_pattern, expr_proc_eval):
            self.logger.warning(f"Invalid characters for eval: '{expr_proc_eval}' (from original '{expr_str_input}')")
            return f"Error: Invalid characters in expression"
        
        self.logger.debug(f"Final string for eval: '{expr_proc_eval}'")
        try:
            safe_builtins = {k: v for k, v in __builtins__.__dict__.items() if k in 
                             ['abs', 'round', 'min', 'max', 'len', 'sum', 'float', 'int', 'str', 'complex', 'pow', 'divmod', 'True', 'False', 'None']}
            result = eval(expr_proc_eval, {"__builtins__": safe_builtins}, allowed_names)
            
            if isinstance(result, complex):
                rp, ip = result.real, result.imag
                rp = round(rp, 12) if abs(rp - round(rp, 12)) < 1e-13 else rp
                ip = round(ip, 12) if abs(ip - round(ip, 12)) < 1e-13 else ip
                if ip == 0: result = rp 
                elif rp == 0: return (f"{ip:g}" if ip != 1 and ip != -1 else "") + "j" if ip != -1 else "-j"
                else: return f"{rp:g}{'+' if ip >= 0 else ''}{ip:g}j"

            if isinstance(result, float):
                if result == int(result): return int(result) 
                for i in range(1, 11): 
                    if abs(result - round(result, i)) < 1e-12: return round(result, i)
                return float(f"{result:.12g}") 
            return result 
        except ZeroDivisionError: return "Error: Division by zero"
        except SyntaxError as e: self.logger.error(f"Syntax error in eval for '{expr_proc_eval}': {e}"); return f"Error: Syntax error"
        except (NameError, TypeError) as e:
            if isinstance(e, NameError) and re.search(r"name '(\w+)' is not defined", str(e)):
                 un = re.search(r"name '(\w+)' is not defined", str(e)).group(1)
                 return f"Error: Unknown function/variable '{un}'"
            self.logger.error(f"Name/Type error in eval for '{expr_proc_eval}': {e}"); return f"Error: Invalid function/op or type ({type(e).__name__})"
        except OverflowError: return "Error: Result too large"
        except Exception as e: self.logger.error(f"General eval error for '{expr_proc_eval}': {e}", exc_info=True); return f"Error: Calculation failed ({type(e).__name__})"

    def update_result_display(self, expression, result_val, is_error_or_info=False, is_complex_result_type=False):
        display_text, fg_color = "", self.settings.get("overlay_text_color", 'black')
        if is_error_or_info: 
            display_text = str(result_val)
            fg_color = 'red' if str(result_val).startswith("Error:") else 'darkorange' 
        elif is_complex_result_type: display_text = str(result_val) 
        else: 
            short_expr = expression if len(expression) < 60 else expression[:57] + "..."
            display_text = f"{short_expr} = {result_val}"
        self.result_label.config(fg=fg_color); self.status_var.set(display_text)
        self.logger.debug(f"Displaying: {display_text}")
        self.auto_resize_overlay()

    def auto_resize_overlay(self):
        if not (hasattr(self, 'overlay') and self.overlay.winfo_exists()): return
        self.overlay.update_idletasks() 
        label_w, label_h = self.result_label.winfo_reqwidth(), self.result_label.winfo_reqheight()
        buttons_w, buttons_h = self.button_frame.winfo_reqwidth(), self.button_frame.winfo_reqheight()
        total_w, total_h = label_w + buttons_w + 20, max(label_h, buttons_h) + 10
        geom_parts = self.overlay.geometry().split('+')
        cur_x, cur_y = (geom_parts[1] if len(geom_parts) > 1 else "50"), (geom_parts[2] if len(geom_parts) > 2 else "50")
        self.overlay.geometry(f"{total_w}x{total_h}+{cur_x}+{cur_y}")

    def add_to_history(self, expression, result):
        entry = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "expression": expression, "result": str(result)}
        if hasattr(self, '_last_sympy_solution_obj') and self._last_sympy_solution_obj is not None:
            entry["sympy_obj"] = self._last_sympy_solution_obj; self._last_sympy_solution_obj = None 
        self.calculation_history.append(entry)

    def show_history_window(self):
        if hasattr(self, 'history_window') and self.history_window.winfo_exists(): self.history_window.lift(); return
        self.history_window = tk.Toplevel(self.root); self.history_window.title("Calculation History")
        self.history_window.geometry("600x450"); self.history_window.configure(bg=self.settings.get("overlay_bg_color", "white"))
        frame = tk.Frame(self.history_window); frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        x_scroll, y_scroll = tk.Scrollbar(frame, orient=tk.HORIZONTAL), tk.Scrollbar(frame, orient=tk.VERTICAL)
        self.history_listbox = tk.Listbox(frame, yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set,
                                         font=(self.settings.get("font_family", "Arial"), 10), selectmode=tk.SINGLE,
                                         bg=self.settings.get("overlay_bg_color", "white"), fg=self.settings.get("overlay_text_color", "black"))
        y_scroll.config(command=self.history_listbox.yview); x_scroll.config(command=self.history_listbox.xview)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y); x_scroll.pack(side=tk.BOTTOM, fill=tk.X); self.history_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        for item in reversed(self.calculation_history): 
            res_s = str(item['result'])
            is_complex = res_s.startswith("x =") or "->" in res_s or "days" in res_s.lower() or \
                         re.match(r"\d{4}-\d{2}-\d{2}", res_s) or re.match(r"(0x[0-9a-fA-F]+|0b[01]+|0o[0-7]+)", res_s, re.IGNORECASE)
            self.history_listbox.insert(tk.END, f"[{item['timestamp']}] {item['expression']} {' => ' if is_complex else ' = '}{res_s}")
        btn_f = tk.Frame(self.history_window, bg=self.settings.get("overlay_bg_color", "white")); btn_f.pack(fill=tk.X, padx=5, pady=5)
        tk.Button(btn_f, text="Copy Expression", command=lambda: self.copy_history_item_part("expression")).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_f, text="Copy Result/Solution", command=lambda: self.copy_history_item_part("result")).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_f, text="Copy as LaTeX", command=lambda: self.copy_history_item_part("latex")).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_f, text="Clear History", command=self.clear_history).pack(side=tk.RIGHT, padx=2)

    def copy_history_item_part(self, part_type):
        if not hasattr(self, 'history_listbox') or not self.history_listbox.winfo_exists(): return
        sel = self.history_listbox.curselection()
        if not sel: messagebox.showwarning("Copy History", "No item selected.", parent=self.history_window); return
        hist_idx = len(self.calculation_history) - 1 - sel[0]
        if not (0 <= hist_idx < len(self.calculation_history)): messagebox.showerror("Copy History", "Error mapping selection.", parent=self.history_window); return
        item = self.calculation_history[hist_idx]
        expr, res = item['expression'], str(item['result'])
        to_copy = ""
        if part_type == "expression": to_copy = expr
        elif part_type == "result": to_copy = res
        elif part_type == "latex":
            lx_expr = expr.replace('sqrt(', r'\sqrt{').replace('^', '^{') 
            lx_expr = re.sub(r'(\w)\^\{([\w.-]+)\}(?!\w)', r'\1^{\2}', lx_expr)
            lx_expr = lx_expr.replace('*', r' \times ')
            lx_expr = re.sub(r'([a-zA-Z0-9\.]+)\s*/\s*([a-zA-Z0-9\.]+)', r'\\frac{\1}{\2}', lx_expr)
            lx_res = res
            if 'sympy_obj' in item and item['sympy_obj']:
                try: import sympy; lx_res = (f"x = {sympy.latex(item['sympy_obj'])}" if res.startswith("x =") else sympy.latex(item['sympy_obj']))
                except Exception as e: self.logger.error(f"Sympy LaTeX err: {e}")
            # Removed Pint specific LaTeX part
            sep = r" \Rightarrow " if res.startswith("x =") else " = "
            to_copy = f"${lx_expr}{sep}{lx_res}$"
        if to_copy and pyperclip: pyperclip.copy(to_copy); self.logger.info(f"Copied from history ({part_type}): {to_copy[:70]}...")
        elif not pyperclip: messagebox.showerror("Error", "Pyperclip library not found.", parent=self.history_window if hasattr(self, 'history_window') else self.root)

    def clear_history(self):
        if messagebox.askyesno("Confirm Clear", "Clear all history?", parent=self.history_window):
            self.calculation_history.clear()
            if hasattr(self, 'history_listbox') and self.history_listbox.winfo_exists(): self.history_listbox.delete(0, tk.END)
            self.logger.info("Calculation history cleared.")

    def show_settings_window(self):
        if hasattr(self, 'settings_window') and self.settings_window.winfo_exists(): self.settings_window.lift(); return
        self.settings_window = tk.Toplevel(self.root); self.settings_window.title("Settings"); self.settings_window.geometry("400x550"); self.settings_window.configure(bg="white")
        tk.Label(self.settings_window, text="Theme:", bg="white").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.theme_var = tk.StringVar(value=self.settings.get("theme_name", "Yellowish"))
        om = OptionMenu(self.settings_window, self.theme_var, *self.themes.keys(), command=lambda sel_theme: self.settings.update({"theme_name": sel_theme}))
        om.config(width=15, bg="white", relief="raised", highlightthickness=1); om["menu"].config(bg="white"); om.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        tk.Label(self.settings_window, text="Font Size:", bg="white").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.font_size_var = tk.IntVar(value=self.settings.get("font_size", 12))
        tk.Spinbox(self.settings_window, from_=8, to=30,textvariable=self.font_size_var,width=5).grid(row=1,column=1,padx=5,pady=5,sticky="ew")
        tk.Label(self.settings_window,text="Overlay BG Color:",bg="white").grid(row=2,column=0,padx=5,pady=5,sticky="w")
        self.bg_color_btn = tk.Button(self.settings_window,text="Choose...",command=self.choose_bg_color,width=10)
        self.bg_color_btn.grid(row=2,column=1,padx=5,pady=5,sticky="ew")
        self.bg_color_preview = tk.Label(self.settings_window,text=" ",bg=self.settings.get("overlay_bg_color","lightyellow"),width=3,relief="sunken")
        self.bg_color_preview.grid(row=2,column=2,padx=5,pady=5)
        tk.Label(self.settings_window,text="Overlay Text Color:",bg="white").grid(row=3,column=0,padx=5,pady=5,sticky="w")
        self.text_color_btn = tk.Button(self.settings_window,text="Choose...",command=self.choose_text_color,width=10)
        self.text_color_btn.grid(row=3,column=1,padx=5,pady=5,sticky="ew")
        self.text_color_preview = tk.Label(self.settings_window,text=" ",bg=self.settings.get("overlay_text_color","black"),width=3,relief="sunken")
        self.text_color_preview.grid(row=3,column=2,padx=5,pady=5)
        tk.Label(self.settings_window,text="Overlay Opacity:",bg="white").grid(row=4,column=0,padx=5,pady=5,sticky="w")
        self.opacity_var = tk.DoubleVar(value=self.settings.get("overlay_opacity",1.0))
        Scale(self.settings_window,from_=0.1,to=1.0,resolution=0.05,orient=tk.HORIZONTAL,variable=self.opacity_var,bg="white",highlightthickness=0,troughcolor='#E0E0E0').grid(row=4,column=1,columnspan=2,padx=5,pady=5,sticky="ew")
        self.always_on_top_var = tk.BooleanVar(value=self.settings.get("always_on_top",True))
        tk.Checkbutton(self.settings_window,text="Always on Top",variable=self.always_on_top_var,bg="white",activebackground="white").grid(row=5,column=0,columnspan=2,padx=5,pady=2,sticky="w")
        self.auto_copy_result_var = tk.BooleanVar(value=self.settings.get("auto_copy_result",False))
        tk.Checkbutton(self.settings_window,text="Auto-copy Result",variable=self.auto_copy_result_var,bg="white",activebackground="white").grid(row=6,column=0,columnspan=2,padx=5,pady=2,sticky="w")
        tk.Label(self.settings_window,text="Monitor Interval (ms):",bg="white").grid(row=7,column=0,padx=5,pady=5,sticky="w")
        self.interval_var = tk.IntVar(value=self.settings.get("monitoring_interval_ms",500))
        tk.Spinbox(self.settings_window,from_=100,to=5000,increment=100,textvariable=self.interval_var,width=7).grid(row=7,column=1,padx=5,pady=5,sticky="ew")
        tk.Label(self.settings_window,text="Max History Items:",bg="white").grid(row=8,column=0,padx=5,pady=5,sticky="w")
        self.max_history_var = tk.IntVar(value=self.settings.get("max_history_items",20))
        tk.Spinbox(self.settings_window,from_=5,to=100,increment=5,textvariable=self.max_history_var,width=5).grid(row=8,column=1,padx=5,pady=5,sticky="ew")
        tk.Button(self.settings_window,text="Apply & Save",command=self.apply_and_save_settings).grid(row=9,column=0,columnspan=3,padx=5,pady=10)
        self.settings_window.grid_columnconfigure(1,weight=1)

    def choose_bg_color(self):
        cc = colorchooser.askcolor(title="Choose BG Color",initialcolor=self.settings.get("overlay_bg_color","lightyellow"),parent=self.settings_window)
        if cc and cc[1]: self.chosen_bg_color_temp, self.bg_color_preview.config(bg=cc[1]), self.theme_var.set("")
    def choose_text_color(self):
        cc = colorchooser.askcolor(title="Choose Text Color",initialcolor=self.settings.get("overlay_text_color","black"),parent=self.settings_window)
        if cc and cc[1]: self.chosen_text_color_temp, self.text_color_preview.config(bg=cc[1]), self.theme_var.set("")

    def apply_and_save_settings(self):
        sel_theme = self.theme_var.get()
        if sel_theme and sel_theme in self.themes: self.apply_theme(sel_theme)
        self.settings["font_size"] = self.font_size_var.get()
        if hasattr(self,'chosen_bg_color_temp'): self.settings["overlay_bg_color"]=self.chosen_bg_color_temp; self.settings["overlay_button_bg_color"]=self.chosen_bg_color_temp; del self.chosen_bg_color_temp
        if hasattr(self,'chosen_text_color_temp'): self.settings["overlay_text_color"]=self.chosen_text_color_temp; del self.chosen_text_color_temp
        self.settings["overlay_opacity"]=self.opacity_var.get(); self.settings["always_on_top"]=self.always_on_top_var.get()
        self.settings["auto_copy_result"]=self.auto_copy_result_var.get(); self.settings["monitoring_interval_ms"]=self.interval_var.get()
        self.settings["max_history_items"]=self.max_history_var.get()
        self.update_overlay_appearance(); self.save_settings()
        if hasattr(self,'settings_window') and self.settings_window.winfo_exists(): self.settings_window.destroy()
        self.logger.info("Settings applied and saved.")

    def toggle_pause_monitoring(self):
        self.monitoring_paused = not self.monitoring_paused
        icon, color, status = ("►",'green',"Paused...") if self.monitoring_paused else ("❚❚",'blue',"Ready...")
        if hasattr(self,'pause_resume_btn') and self.pause_resume_btn.winfo_exists(): self.pause_resume_btn.config(text=icon,fg=color)
        self.status_var.set(status); self.logger.info(f"Monitoring {'paused' if self.monitoring_paused else 'resumed'}.")
        self.auto_resize_overlay()

    def on_close(self):
        self.logger.info("Shutting down..."); self.stop_event.set(); self.save_settings()
        if self.monitor_thread and self.monitor_thread.is_alive(): self.monitor_thread.join(timeout=1.0)
        for attr in ['history_window','settings_window','overlay']:
            if hasattr(self,attr): 
                win = getattr(self,attr)
                if win and win.winfo_exists(): 
                    try: win.destroy()
                    except tk.TclError: pass
        if self.root and self.root.winfo_exists(): 
            try: self.root.quit(); self.root.destroy()
            except tk.TclError: pass
        self.logger.info("Application closed.")

if __name__ == "__main__":
    if not pyperclip: print("Exiting: Pyperclip library is required.")
    else:
        print("Clipboard Calculator X starting...")
        print("Features: Math, Equations (sympy), Dates (dateutil), Bases, Stats.") # Removed Units
        print("See overlay buttons (❚❚/►, H, S, X) and settings for more.")
        app = ClipboardCalculator()
        try: app.root.mainloop()
        except KeyboardInterrupt: print("\nInterrupted."); app.on_close()
        except Exception as e:
            logger = app.logger if hasattr(app,'logger') else logging.getLogger()
            logger.critical(f"Unhandled main loop exception: {e}", exc_info=True)
            if hasattr(app,'on_close'): app.on_close()


