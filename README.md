# CalcX - The Clipboard Calculator

**CalcX** is a powerful, always-on-top clipboard calculator that monitors your clipboard for mathematical expressions, equations, date calculations, base conversions, and statistical queries. When a recognized query is copied, CalcX automatically evaluates it and displays the result in a convenient, draggable overlay.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

* **Instant Calculations:** Automatically evaluates expressions copied to the clipboard.
* **Overlay Display:** Shows results in a sleek, movable, always-on-top window.
* **Wide Range of Solvers:**
    * **Standard Math:** Arithmetic, percentages (`50% of 200`, `75%`), functions (`sqrt`, `sin`, `cos`, `log`, `pi`, `e`), powers (`^` or `**`).
    * **Equation Solving:** Solves for `x` in algebraic equations (e.g., `2x + 5 = 10`, `x^2 - 4*x = -3`) using Sympy.
    * **Date & Time Calculations:** Parses and computes date/time expressions (e.g., `today + 5 days`, `2 weeks ago`, `days between 2024-01-01 and 2024-03-01`, `now - 3 months`) using python-dateutil.
    * **Base Conversions:** Converts numbers between decimal, hexadecimal (`0x...`, `hex(...)`), binary (`0b...`, `bin(...)`), and octal (`0o...`, `oct(...)`) (e.g., `hex(255)`, `0b1101 to dec`).
    * **Statistical Functions:** Calculates mean, median, mode, standard deviation, and variance (e.g., `mean(1,2,3,4,5)`, `stdev(10 12 15 10 13)`).
* **Calculation History:**
    * View a history of your calculations.
    * Copy expressions, results, or even LaTeX formatted equations from history.
* **Customizable Interface:**
    * Multiple themes (Light, Dark, Yellowish).
    * Adjust font size, overlay colors (background, text), and opacity.
    * Toggle "Always on Top" and "Auto-copy Result" features.
    * Configure clipboard monitoring interval and history length.
* **User-Friendly Controls:**
    * Pause/Resume clipboard monitoring.
    * Quick access to History and Settings.
    * Easy close button.
* **Persistent Settings:** Saves your preferences and overlay position in `CalcX_settings.json`.

## Download Executable (Windows)

For Windows users, a pre-compiled executable is available:

* **[Download CalcX_Setup.exe from MediaFire](https://www.mediafire.com/file/io2bdj9t2bhznyg/CalcX_Setup.exe/file)**

## How It Works

CalcX runs in the background, periodically checking the content of your system clipboard. If the copied text matches a pattern for a mathematical expression, equation, date query, or other supported calculation, it processes the query and displays the input and result (or error message) in the overlay window.

The overlay can be dragged to any position on your screen. Settings and calculation history are accessible via buttons on the overlay itself.

## Types of Queries Solved (Examples)

Simply copy any of the following to your clipboard:

* **Basic Math:**
    * `2 + 2 * 10 / 4`
    * `15% of 300`
    * `sqrt(16) + sin(pi/2)`
    * `(10 + 5) * 3`
    * `2^10`
    * `100 * 5%`
* **Equation Solving (for 'x'):**
    * `2x + 5 = 15`
    * `x^2 - 9 = 0`
    * `3*x - 7 = 2*x + 3`
    * `sqrt(x) = 4`
* **Date & Time Calculations:**
    * `today`
    * `now + 2 weeks`
    * `yesterday - 3 months`
    * `2025-12-25 - 60 days`
    * `days between 2024-06-01 and 2024-08-15`
    * `30 days ago`
    * `January 15 2023 + 1 year 2 months 3 days`
* **Base Conversions:**
    * `hex(255)`
    * `0b11011010 to dec`
    * `172 to hex`
    * `0o77 to bin`
* **Statistical Functions:**
    * `mean(1, 2, 3, 4, 5)`
    * `median(10, 5, 20, 15)`
    * `stdev(2, 4, 4, 4, 5, 5, 7, 9)`
    * `variance(10 12 11 13 10)`

## Interface Overview

The main interface is a small overlay window:

* **Result Display Area:** Shows the current expression and its result, or status messages. Click and drag this area to move the overlay.
* **Buttons (right side):**
    * **❚❚ / ► (Pause/Resume):** Toggles clipboard monitoring.
    * **H (History):** Opens the calculation history window.
    * **S (Settings):** Opens the settings window.
    * **X (Close):** Shuts down CalcX.

## Installation (from Source)

If you prefer to run from source or are not on Windows:

1.  **Prerequisites:**
    * Python 3.6 or newer is recommended.
    * Tkinter (usually included with Python installations. If not, you may need to install it, e.g., `sudo apt-get install python3-tk` on Debian/Ubuntu).

2.  **Clone the Repository (Optional):**
    ```bash
    git clone [https://github.com/NOOB4EVER69/CalcX.git](https://github.com/NOOB4EVER69/CalcX.git)
    cd CalcX
    ```
    Alternatively, download the source code (e.g., `calcx.py`).

3.  **Install Dependencies:**
    Open a terminal or command prompt and run:
    ```bash
    pip install -r requirements.txt
    ```
    This will install `pyperclip`, `sympy`, and `python-dateutil`.

## Running CalcX (from Source)

Navigate to the directory containing the script and run:

```bash
python calcx.py
```

(Assuming you name your main Python file `calcx.py`).

Upon first run, `CalcX_settings.json` will be created to store your preferences.

## Customization

Most customization options are available through the **Settings (S)** window:

* **Theme:** Choose from predefined themes.
* **Font Size:** Adjust the font size for the overlay text.
* **Overlay BG/Text Color:** Manually pick background and text colors (overrides theme).
* **Overlay Opacity:** Make the overlay more or less transparent.
* **Always on Top:** Keep the overlay visible above other windows.
* **Auto-copy Result:** Automatically copy the calculated result back to the clipboard.
* **Monitor Interval (ms):** How frequently to check the clipboard (in milliseconds).
* **Max History Items:** Number of calculations to store in history.

Settings are saved automatically when changed or when CalcX closes.

## Dependencies

* **Tkinter:** For the graphical user interface.
* **Pyperclip:** For cross-platform clipboard access.
* **Sympy:** For symbolic mathematics, enabling equation solving. (Loaded on demand)
* **python-dateutil:** For advanced date and time parsing and calculations. (Loaded on demand)
* **statistics:** (Built-in Python module) For statistical functions. (Loaded on demand)

## Contributing

Contributions, issues, and feature requests are welcome! Please feel free to fork the repository, make changes, and submit a pull request. If you encounter any bugs or have ideas for new features, please open an issue.

## License


