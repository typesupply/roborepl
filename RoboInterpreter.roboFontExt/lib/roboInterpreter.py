documentation = """
RoboREPL 0.0 alphamcalpha
=========================

Namespace Injections
--------------------
help : This.
settings : An editor settings manager. Type settings.help for documentation.

To Do:
------
- finish settings
- rename extension
- cursor drawing
- universal leading
- RF code key commands
- completion
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

# --------
# Settings
# --------

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
        obj.postNotification({self.key : value})


settingsManagerDoc = """
=======================
Editor Settings Manager
=======================

Attributes
----------
help : This.
windowWidth : The number of characters per line. This must be a positive integer.
windowHeight : The number of rows per window. This must be a positive integer.
fontName : The font name. Must be a string.
fontSize : The font size. Must be a positive number.
fontLeading : The font leading percentage. Must be a positive number.
colorCode : The color for code text. Must be a color tuple.
colorStdout : The color for stdout text. Must be a color tuple.
colorStderr : The color for stderr text. Must be a color tuple.
colorBackground : The background color. Must be a color tuple.
# bannerVersion
# bannerCopyright
# bannerGreeting
# injections

Color tuples are tuples containing four positive numbers between 0 and 1.

Methods
-------
availableFonts() : Names of avaiable monospaced fonts.
""".strip()


class PyREPLSettings(object):

    def __init__(self):
        self._dispatcher = NotificationCenter()

    def __repr__(self):
        return "<Editor Settings Manager. Type settings.help for documentation.>"

    def _get_help(self):
        print settingsManagerDoc

    help = property(_get_help)

    def addObserver(self, obj, methodName):
        self._dispatcher.addObserver(obj, methodName, observable=self)

    def removeObserver(self, obj):
        self._dispatcher.removeObserver(obj, None, self)

    def postNotification(self, data):
        self._dispatcher.postNotification("PyREPL.SettingsChanged", self, data)

    windowWidth = settingsProperty("windowWidth", settingsWindowSizeValidator)
    windowHeight = settingsProperty("windowHeight", settingsWindowSizeValidator)
    fontName = settingsProperty("fontName", settingsStringValidator)
    fontSize = settingsProperty("fontSize", settingsPositiveNumberValidator)
    fontLeading = settingsProperty("fontLeading", settingsPositiveNumberValidator)
    colorCode = settingsProperty("colorCode", settingsColorValidator)
    colorStdout = settingsProperty("colorStdout", settingsColorValidator)
    colorStderr = settingsProperty("colorStderr", settingsColorValidator)
    colorBackground = settingsProperty("colorBackground", settingsColorValidator)

    def editorItems(self):
        d = dict(
            fontName=self.fontName,
            fontSize=self.fontSize,
            fontLeading=self.fontLeading,
            colorCode=self.colorCode,
            colorStdout=self.colorStdout,
            colorStderr=self.colorStderr,
            colorBackground=self.colorBackground,
        )
        return d.items()

    def availableFonts(self):
        manager = NSFontManager.sharedFontManager()
        for name in manager.availableFonts():
            font = NSFont.fontWithName_size_(name, 10)
            if font.isFixedPitch():
                print name


defaultSettings = dict(
    bannerVersion=False,
    bannerCopyright=False,
    bannerGreeting="",
    windowWidth=80,
    windowHeight=24,
    fontName="QueueMono-Light",
    fontSize=20,
    fontLeading=1.2,
    colorCode=(0, 0, 0, 1),
    colorStderr=(1, 0, 0, 1),
    colorStdout=(0, 0, 1, 1),
    colorBackground=(1, 1, 1, 1),
    injections={}
)

try:
    from mojo import extensions

    defaultStub = "com.typesupply.RoboREPL."

    d = {}
    for k, v in defaultSettings.items():
        d[defaultStub + k] = v
    extensions.registerExtensionsDefaults(d)

    def getDefaultValue(key):
        return extensions.getExtensionDefault(defaultStub + key)

    def setDefaultValue(key, value):
        extensions.setExtensionDefault(defaultStub + value)

except ImportError:

    def getDefaultValue(key):
        return defaultSettings[key]

    def setDefaultValue(key, value):
        defaultSettings[key] = value

settingsManager = PyREPLSettings()

# ------
# Window
# ------

class PyREPLWindow(object):

    def __init__(self):
        self.w = vanilla.Window((600, 400), "RoboREPL")
        self.w.editor = PyREPLTextEditor((0, 0, 0, 0))
        self.loadSettings()

        window = self.w.getNSWindow()
        window.setBackgroundColor_(NSColor.clearColor())

        settingsManager.addObserver(self, "settingsChangedCallback")
        self.w.bind("close", self.windowClosedCallback)

        self.w.open()

    def windowClosedCallback(self, sender):
        settingsManager.removeObserver(self)

    def loadSettings(self):
        class DummyNotification(object): pass

        for key, value in settingsManager.editorItems():
            n = DummyNotification()
            n.data = {key : value}
            self.settingsChangedCallback(n)

    def settingsChangedCallback(self, notification):
        key, value = notification.data.items()[0]
        editorMethods = dict(
            fontName=self.w.editor.setFontName,
            fontSize=self.w.editor.setFontSize,
            fontLeading=self.w.editor.setFontLeading,
            colorCode=self.w.editor.setCodeColor,
            colorStdout=self.w.editor.setStdoutColor,
            colorStderr=self.w.editor.setStderrColor,
            colorBackground=self.w.editor.setBackgroundColor,
        )
        if key in editorMethods:
            editorMethods[key](value)
        if key in ("fontName", "fontSize", "fontLeading", "windowWidth", "windowHeight"):
            x, y, w, h = self.w.getPosSize()
            w, h = self.w.editor.getCharacterBox()
            width = w * settingsManager.windowWidth
            height = h * settingsManager.windowHeight
            self.w.setPosSize((x, y, width, height), animate=True)


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
        self._lineHeight = 30

        self._console = InteractiveConsole(locals=namespaceInjections)
        self._stderr = PseudoUTF8Output(self.writeStderr_)
        self._stdout = PseudoUTF8Output(self.writeStdout_)
        self._prompt = sys.ps1

        self._minInsertionPoint = 0

        self._history = [""]
        self._historyIndex = 1

        return self

    # Settings

    def getCharacterBox(self):
        font = self.font()
        glyph = font.glyphWithName_("space")
        glyphWidth = font.advancementForGlyph_(glyph).width
        return glyphWidth, self._lineHeight

    def setFontLeading_(self, value):
        self._lineHeight = value

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

    def scrollToEnd(self):
        index = self.textLength()
        self.scrollRangeToVisible_((index, 0))
        self.setSelectedRange_((index, 0))

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
        paragraphStyle = NSMutableParagraphStyle.alloc().init()
        paragraphStyle.setLineSpacing_(self._lineHeight - self.font().pointSize())
        attrs = {
            NSForegroundColorAttributeName : color,
            NSFontAttributeName : self.font(),
            NSParagraphStyleAttributeName : paragraphStyle
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
        textView.writePrompt()
        scrollView = self.getNSScrollView()
        scrollView.setDrawsBackground_(False)
        scrollView.setBorderType_(NSNoBorder)
        self._fontName = "Menlo-Regular"
        self._fontSize = 10
        self._fontLeading = 1.2

    def getCharacterBox(self):
        return self.getNSTextView().getCharacterBox()

    def setFontName(self, value):
        self._fontName = value
        self._updateFont()

    def setFontSize(self, value):
        self._fontSize = value
        self._updateFont()

    def setFontLeading(self, value):
        self._fontLeading = value
        self._updateFont()

    def _updateFont(self):
        view = self.getNSTextView()
        font = NSFont.fontWithName_size_(self._fontName, self._fontSize)
        if font is not None:
            view.setFont_(font)
        view.setFontLeading_(self._fontSize * self._fontLeading)

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

try:
    from mojo import roboFont
    namespaceInjections.update({
        "AllFonts" : roboFont.AllFonts,
        "CurrentFont" : roboFont.CurrentFont,
        "CurrentGlyph" : roboFont.CurrentGlyph,
        "OpenFont" : roboFont.OpenFont,
        "NewFont" : roboFont.NewFont,
    })
except ImportError:
    pass

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
