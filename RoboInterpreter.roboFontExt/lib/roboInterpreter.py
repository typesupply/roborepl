documentation = """
RoboREPL 0.0 alphamcalpha
=========================

Namespace Injections
--------------------
help : This.
settings : An editor settings manager. Type "settings.help" for documentation.

To Do
-----
- cmd-k doesn't work in RF
- rename extension
- cursor drawing
- universal leading
- RF code key commands
- completion
- themes
    - basic
    - classic
    - robofog
- use a floating panel
""".strip()

# This was inspired by the PyObjC Interpreter demo.

import sys
from code import InteractiveConsole
from defcon.tools.notifications import NotificationCenter
from AppKit import *
import vanilla
from vanilla.vanillaTextEditor import VanillaTextEditorDelegate
from defconAppKit.windows.baseWindow import BaseWindowController

try:
    sys.ps1
except AttributeError:
    sys.ps1 = ">>> "
try:
    sys.ps2
except AttributeError:
    sys.ps2 = "... "

try:
    import mojo
    inRoboFont = True
except ImportError:
    inRoboFont = False

# --------
# Settings
# --------

defaultStartupCode = """
# This script will be executed when the interpreter is started.
# It will be executed in the same namespace as your later code
# will be executed in, so you can define variables, import
# modules and anything else that you want.
""".lstrip()

if inRoboFont:
    defaultStartupCode += """
CF = CurrentFont
CG = CurrentGlyph
AF = AllFonts
OF = OpenFont
NF = NewFont
"""

defaultSettings = dict(
    bannerGreeting="Welcome to RoboREPL! Type \"help\" for help.",
    windowWidth=80,
    windowHeight=24,
    tabString="  ",
    fontName="QueueMono-Light",
    fontSize=20,
    colorCode=(0, 0, 0, 1),
    colorStderr=(1, 0, 0, 1),
    colorStdout=(0, 0, 1, 1),
    colorBackground=(1, 1, 1, 1),
    startupCode=defaultStartupCode
)

class PyREPLSettingsError(Exception): pass


def settingsStringValidator(value):
    return isinstance(value, basestring)

def settingsNumberValidator(value):
    return isinstance(value, (int, float))

def settingsPositiveNumberValidator(value):
    if not settingsNumberValidator(value):
        return False
    return value >= 0

def settingsWindowSizeValidator(value):
    if not isinstance(value, int):
        return False
    return value > 0

def settingsColorValidator(value):
    if not isinstance(value, (tuple, list)):
        return False
    if len(value) != 4:
        return False
    for v in value:
        if not settingsPositiveNumberValidator(v):
            return False
        if v < 0 or v > 1:
            return False
    return True

class settingsProperty(object):

    def __init__(self, key, validator=None, doc=""):
        self.key = key
        self.validator = validator
        self.__doc__ = doc

    def __get__(self, obj, cls):
        return getDefaultValue(self.key)

    def __set__(self, obj, value):
        if self.validator is not None:
            valid = self.validator(value)
            if not valid:
                raise PyREPLSettingsError("%s must be the right value type." % self.key)
        setDefaultValue(self.key, value)
        obj.postNotification(data={self.key : value})


settingsManagerDoc = """
=========================
RoboREPL Settings Manager
=========================

Attributes
----------
help : This.
tabString : Whitespace to insert when the tab key is pressed. Must be a string.
windowWidth : The number of characters per line. Must be a positive integer.
windowHeight : The number of rows per window. Must be a positive integer.
fontName : The font name. Must be a string.
fontSize : The font size. Must be a positive number.
colorCode : The color for code text. Must be a color tuple.
colorStdout : The color for stdout text. Must be a color tuple*.
colorStderr : The color for stderr text. Must be a color tuple*.
colorBackground : The background color. Must be a color tuple*.
bannerGreeting** : The message displayed at startup. Must be a string.
startupCode** : Python code to be executed at startup. Must be a string.
availableFonts : Names of avaiable monospaced fonts. This is read only.

Methods
-------
editStartupCode() : Edit the startup code.

*Color tuples are tuples containing four positive numbers between 0 and 1.
**Only applies to new windows.
""".strip()


class PyREPLSettings(object):

    def __init__(self):
        self._dispatcher = NotificationCenter()

    def __repr__(self):
        return "<Editor Settings Manager. Type \"settings.help\" for documentation.>"

    def _get_help(self):
        print settingsManagerDoc

    help = property(_get_help)

    def addObserver(self, obj, methodName, notification="PyREPL.SettingsChanged"):
        self._dispatcher.addObserver(obj, methodName, notification=notification, observable=self)

    def removeObserver(self, obj, notification="PyREPL.SettingsChanged"):
        self._dispatcher.removeObserver(obj, notification, self)

    def postNotification(self, notification="PyREPL.SettingsChanged", data=None):
        self._dispatcher.postNotification(notification, self, data)

    windowWidth = settingsProperty("windowWidth", settingsWindowSizeValidator)
    windowHeight = settingsProperty("windowHeight", settingsWindowSizeValidator)
    fontName = settingsProperty("fontName", settingsStringValidator)
    fontSize = settingsProperty("fontSize", settingsPositiveNumberValidator)
    colorCode = settingsProperty("colorCode", settingsColorValidator)
    colorStdout = settingsProperty("colorStdout", settingsColorValidator)
    colorStderr = settingsProperty("colorStderr", settingsColorValidator)
    colorBackground = settingsProperty("colorBackground", settingsColorValidator)
    bannerGreeting = settingsProperty("bannerGreeting", settingsStringValidator)
    startupCode = settingsProperty("startupCode", settingsStringValidator)
    tabString = settingsProperty("tabString", settingsStringValidator)

    def editorItems(self):
        d = dict(
            fontName=self.fontName,
            fontSize=self.fontSize,
            colorCode=self.colorCode,
            colorStdout=self.colorStdout,
            colorStderr=self.colorStderr,
            colorBackground=self.colorBackground,
            tabString=self.tabString
        )
        return d.items()

    def _get_availableFonts(self):
        manager = NSFontManager.sharedFontManager()
        for name in manager.availableFonts():
            font = NSFont.fontWithName_size_(name, 10)
            if font.isFixedPitch():
                print name

    availableFonts = property(_get_availableFonts)

    def editStartupCode(self):
        self.postNotification(notification="PyREPL.ShowStartupCodeEditor")


if inRoboFont:
    defaultStub = "com.typesupply.RoboREPL."

    d = {}
    for k, v in defaultSettings.items():
        d[defaultStub + k] = v
    mojo.extensions.registerExtensionDefaults(d)

    def getDefaultValue(key):
        return mojo.extensions.getExtensionDefault(defaultStub + key)

    def setDefaultValue(key, value):
        mojo.extensions.setExtensionDefault(defaultStub + key, value)

else:
    def getDefaultValue(key):
        return defaultSettings[key]

    def setDefaultValue(key, value):
        defaultSettings[key] = value

settingsManager = PyREPLSettings()

# ------
# Window
# ------

class PyREPLWindow(BaseWindowController):

    def __init__(self):
        self.w = vanilla.FloatingWindow((600, 400), "RoboREPL")
        self.w.editor = PyREPLTextEditor((0, 0, 0, 0))
        self.loadSettings()
        self.w.editor.startSession(settingsManager.bannerGreeting, settingsManager.startupCode)

        window = self.w.getNSWindow()
        window.setBackgroundColor_(NSColor.clearColor())

        settingsManager.addObserver(self, "settingsChangedCallback")
        settingsManager.addObserver(self, "showStartupCodeEditorCallback", "PyREPL.ShowStartupCodeEditor")
        self.w.bind("close", self.windowClosedCallback)

        self.w.open()
        self.w.makeKey()

    def windowClosedCallback(self, sender):
        settingsManager.removeObserver(self)
        settingsManager.removeObserver(self, notification="PyREPL.ShowStartupCodeEditor")

    def loadSettings(self):
        class DummyNotification(object): pass

        for key, value in settingsManager.editorItems():
            n = DummyNotification()
            n.data = {key : value}
            self.settingsChangedCallback(n)

    def settingsChangedCallback(self, notification):
        key, value = notification.data.items()[0]
        editorMethods = dict(
            tabString=self.w.editor.setTabString,
            fontName=self.w.editor.setFontName,
            fontSize=self.w.editor.setFontSize,
            colorCode=self.w.editor.setCodeColor,
            colorStdout=self.w.editor.setStdoutColor,
            colorStderr=self.w.editor.setStderrColor,
            colorBackground=self.w.editor.setBackgroundColor,
        )
        if key in editorMethods:
            editorMethods[key](value)
        if key in ("fontName", "fontSize", "windowWidth", "windowHeight"):
            x, y, w, h = self.w.getPosSize()
            w, h = self.w.editor.getCharacterBox()
            width = w * settingsManager.windowWidth
            height = h * settingsManager.windowHeight
            self.w.setPosSize((x, y, width, height), animate=False)

    def showStartupCodeEditorCallback(self, notification):
        PyREPLStatupCodeEditor(self.w)


class PyREPLStatupCodeEditor(object):

    def __init__(self, parentWindow):
        self.w = vanilla.Sheet((600, 700), minSize=(300, 300), parentWindow=parentWindow)
        if inRoboFont:
            from lib.scripting.codeEditor import CodeEditor as codeEditorClass
        else:
            codeEditorClass = vanilla.TextEditor
        self.w.editor = codeEditorClass((15, 15, -15, -50), settingsManager.startupCode)
        self.w.cancelButton = vanilla.Button((-165, -35, -95, 20), "Cancel", callback=self.cancelButtonCallback)
        self.w.applyButton = vanilla.Button((-85, -35, -15, 20), "Apply", callback=self.applyButtonCallback)
        self.w.cancelButton.bind(".", ["command"])
        self.w.open()

    def cancelButtonCallback(self, sender):
        self.w.close()

    def applyButtonCallback(self, sender):
        text = self.w.editor.get()
        settingsManager.startupCode = text
        self.w.close()

# ------
# Editor
# ------

class PyREPLTextView(NSTextView):

    def init(self):
        self = super(PyREPLTextView, self).init()
        self.setDelegate_(self)

        self.setDrawsBackground_(True)

        self._codeColor = NSColor.blackColor()
        self._stderrColor = NSColor.blackColor()
        self._stdoutColor = NSColor.blackColor()

        self._console = InteractiveConsole(locals=namespaceInjections)
        self._stderr = PseudoUTF8Output(self.writeStderr_)
        self._stdout = PseudoUTF8Output(self.writeStdout_)
        self._prompt = sys.ps1

        self._tabString = "  "

        self._minInsertionPoint = 0

        self._history = [""]
        self._historyIndex = 1

        return self

    # Settings

    def setTabString_(self, value):
        self._tabString = value

    def getCharacterBox(self):
        font = self.font()
        glyph = font.glyphWithName_("space")
        glyphWidth = font.advancementForGlyph_(glyph).width
        return glyphWidth, self.font().pointSize()

    def setCodeColor_(self, color):
        self._codeColor = color
        self.setTextColor_(color)
        self.setInsertionPointColor_(color)

    def setStdoutColor_(self, color):
        self._stdoutColor = color

    def setStderrColor_(self, color):
        self._stderrColor = color

    # Raw Text

    def rawText(self):
        return self.textStorage().mutableString()

    def textLength(self):
        return len(self.rawText())

    # Input

    def scrollToEnd(self):
        index = self.textLength()
        self.scrollRangeToVisible_((index, 0))
        self.setSelectedRange_((index, 0))

    def keyDown_(self, event):
        if event.modifierFlags() & NSCommandKeyMask and event.characters() == "k":
            self.clear()
        else:
            return super(PyREPLTextView, self).keyDown_(event)

    def insertNewline_(self, sender):
        line = self.currentLine()
        self.writeCode_("\n")
        self.executeLine_(line)
        self.writePrompt()

    insertNewlineIgnoringFieldEditor_ = insertNewline_

    def insertTab_(self, sender):
        self.writeLine_withColor_(self._tabString, self._codeColor)

    def moveDown_(self, sender):
        self._historyIndex += 1
        if self._historyIndex >= len(self._history):
            self._historyIndex = len(self._history)
            NSBeep()
        else:
            self._insertHistoryLine()

    def moveUp_(self, sender):
        self._historyIndex -= 1
        if self._historyIndex <= 0:
            self._historyIndex = 0
            NSBeep()
        else:
            self._insertHistoryLine()

    def _insertHistoryLine(self):
        text = self._history[self._historyIndex]
        text = self.makeAttributedString_withColor_(text, self._codeColor)
        begin = self._minInsertionPoint
        length = self.textLength() - begin
        textStorage = self.textStorage()
        textStorage.replaceCharactersInRange_withAttributedString_((begin, length), text)

    # Output

    def makeAttributedString_withColor_(self, text, color):
        attrs = {
            NSForegroundColorAttributeName : color,
            NSFontAttributeName : self.font()
        }
        text = NSAttributedString.alloc().initWithString_attributes_(
            text,
            attrs
        )
        return text

    def writeLine_withColor_(self, line, color):
        line = self.makeAttributedString_withColor_(line, color)
        self.textStorage().appendAttributedString_(line)
        self.scrollToEnd()

    def writePrompt(self):
        self.writeCode_(self._prompt)
        self._minInsertionPoint = self.textLength()

    def writeCode_(self, text):
        self.writeLine_withColor_(text, self._codeColor)

    def writeStderr_(self, text):
        self.writeLine_withColor_(text, self._stderrColor)

    def writeStdout_(self, text):
        self.writeLine_withColor_(text, self._stdoutColor)

    def clear(self):
        self.setString_("")
        self.writePrompt()

    # Execution

    def runSource_(self, source):
        save = (sys.stdout, sys.stderr)
        sys.stdout = self._stdout
        sys.stderr = self._stderr
        try:
            self._console.runsource(source)
        finally:
            sys.stdout, sys.stderr = save

    def currentLine(self):
        line = self.rawText().splitlines()[-1]
        line = line[len(self._prompt):]
        return line

    def executeLine_(self, line):
        if line == "help":
            self.writeStdout_(documentation)
            self.writeCode_("\n")
            return
        self._history.append(line)
        self._historyIndex = len(self._history)
        save = (sys.stdout, sys.stderr)
        sys.stdout = self._stdout
        sys.stderr = self._stderr
        more = False
        try:
            more = self._console.push(line)
            if more:
                self._prompt = sys.ps2
            else:
                self._prompt = sys.ps1
        except:
            self._prompt = sys.ps1
        finally:
            sys.stdout, sys.stderr = save

    # Selection, Insertion Point

    def textView_willChangeSelectionFromCharacterRange_toCharacterRange_(self, textView, fromRange, toRange):
        begin, length = toRange
        if length == 0:
            if begin < self._minInsertionPoint:
                NSBeep()
                begin = self._minInsertionPoint
            toRange = (begin, length)
        return toRange

    def textView_shouldChangeTextInRange_replacementString_(self, textView, aRange, newString):
        begin, length = aRange
        if begin < self._minInsertionPoint:
            return False
        return True

    # def drawInsertionPointInRect_color_turnedOn_(self, rect, color, turnedOn):
    #     (x, y), (w, h) = rect
    #     w = self._glyphWidth
    #     rect = ((x, y), (w, h))
    #     if turnedOn:
    #         color.set()
    #         NSRectFill(rect)
    #     else:
    #         self.setNeedsDisplayInRect_avoidAdditionalLayout_(rect, False)

    # Auto Completion

    def textView_completions_forPartialWordRange_indexOfSelectedItem_(self, textView, completions, range, index):
        return [], 0


class PyREPLTextEditor(vanilla.TextEditor):

    nsTextViewClass = PyREPLTextView

    def __init__(self, *args, **kwargs):
        super(PyREPLTextEditor, self).__init__(*args, **kwargs)
        textView = self.getNSTextView()
        scrollView = self.getNSScrollView()
        scrollView.setDrawsBackground_(False)
        scrollView.setBorderType_(NSNoBorder)
        self._fontName = "Menlo-Regular"
        self._fontSize = 10

    def startSession(self, banner=None, startupCode=None):
        textView = self.getNSTextView()
        if banner:
            textView.writeStdout_(banner)
            textView.writeStdout_("\n")
        if startupCode:
            for line in startupCode.splitlines():
                textView.runSource_(line)
        textView.writePrompt()

    def getCharacterBox(self):
        return self.getNSTextView().getCharacterBox()

    def setTabString(self, value):
        self.getNSTextView().setTabString_(value)

    def setFontName(self, value):
        self._fontName = value
        self._updateFont()

    def setFontSize(self, value):
        self._fontSize = value
        self._updateFont()

    def _updateFont(self):
        view = self.getNSTextView()
        font = NSFont.fontWithName_size_(self._fontName, self._fontSize)
        if font is not None:
            view.setFont_(font)

    def setCodeColor(self, value):
        color = self._makeColor(value)
        self.getNSTextView().setCodeColor_(color)

    def setStdoutColor(self, value):
        color = self._makeColor(value)
        self.getNSTextView().setStdoutColor_(color)

    def setStderrColor(self, value):
        color = self._makeColor(value)
        self.getNSTextView().setStderrColor_(color)

    def setBackgroundColor(self, value):
        color = self._makeColor(value)
        self.getNSTextView().setBackgroundColor_(color)

    def _makeColor(self, value):
        r, g, b, a = value
        return NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, a)


# -----------
# Interpreter
# -----------

namespaceInjections = {
    "settings" : settingsManager
}

if inRoboFont:
    namespaceInjections.update({
        "AllFonts" : mojo.roboFont.AllFonts,
        "CurrentFont" : mojo.roboFont.CurrentFont,
        "CurrentGlyph" : mojo.roboFont.CurrentGlyph,
        "OpenFont" : mojo.roboFont.OpenFont,
        "NewFont" : mojo.roboFont.NewFont,
    })


class PseudoUTF8Output(object):

    softspace = 0

    def __init__(self, writemethod):
        self._write = writemethod

    def write(self, s):
        if not isinstance(s, unicode):
            s = s.decode("utf-8", "replace")
        self._write(s)

    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def flush(self):
        pass

    def isatty(self):
        return True


if __name__ == "__main__":
    from vanilla.test.testTools import executeVanillaTest
    executeVanillaTest(PyREPLWindow)
