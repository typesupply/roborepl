documentation = u"""
============
RoboREPL 0.4
============

An interactive Python interpreter for RoboFont.
You type some code in it and it will be executed.

To get help, type "help", but you already figured that out.
To learn about changing settings, type "settings.help".

Key Commands
------------
\u2318K : Clear the window.
\u2318C : Copy the latest stdout/stderr output to the pasteboard.
TAB : Insert the value defined in settings.tabString at the cursor.
\u21E7+TAB : Remove the value defined in settings.tabString before the cursor.
ESC : Display auto-completion suggestions.
\u2318F : Initiate a text search. (Note: replacing found text is not supported.) 
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

try:
    import jedi
    haveJedi = True
    variableChars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_"
except ImportError:
    haveJedi = False

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
    fontName="Menlo-Regular",
    fontSize=20,
    showInvisibleCharacters=False,
    startupCode=defaultStartupCode,
    userThemes={}
)

defaultThemes = dict(
    default=dict(
        colorCode=(0, 0, 0, 1),
        colorStderr=(1, 0, 0, 1),
        colorStdout=(0, 0, 1, 1),
        colorBackground=(1, 1, 1, 1)
    ),
    classic=dict(
        colorCode=(0, 1, 0, 1),
        colorStderr=(1, 0, 0, 1),
        colorStdout=(1, 1, 1, 1),
        colorBackground=(0, 0, 0, 0.8)
    ),
    robofog=dict(
        colorCode=(0, 0, 0, 1),
        colorStderr=(0, 0, 0, 1),
        colorStdout=(0, 0, 0, 1),
        colorBackground=(1, 1, 1, 1)
    )
)

defaultSettings.update(defaultThemes["default"])


class PyREPLSettingsError(Exception): pass


def settingsBoolValidator(value):
    return isinstance(value, bool)

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
=================
RoboREPL Settings
=================

All settings are handled through the "settings" object.
You get a setting like this:

>>> settings.fontSize
20

You set a settings like this:

>>> settings.fontSize = 15

Available Settings
------------------

- Window Settings
settings.windowWidth : The number of characters per line. Must be a positive integer.
settings.windowHeight : The number of rows per window. Must be a positive integer.

- Fonts
settings.fontName : The font name. Must be a string.
settings.fontSize : The font size. Must be a positive number.
settings.availableFonts : Names of installed monospaced fonts. This is read only.
settings.showInvisibleCharacters : Show invisible characters. Must be a boolean.

- Colors
settings.colorCode : The color for code text. Must be a color tuple.
settings.colorStdout : The color for stdout text. Must be a color tuple*.
settings.colorStderr : The color for stderr text. Must be a color tuple*.
settings.colorBackground : The background color. Must be a color tuple*.

- Themes
loadTheme("name") : Load a theme. The defaults are "default", "classic" and "robofog".
saveTheme("name") : Save the current theme. This can then be loaded with "settings.loadTheme".

- Text
settings.tabString : Whitespace to insert when the tab key is pressed. Must be a string.
settings.bannerGreeting** : The message displayed at startup. Must be a string.

- Startup Code
settings.startupCode** : Python code to be executed at startup. Must be a string.
editStartupCode() : Edit the startup code.

*Color tuples are tuples containing four positive numbers between 0 and 1.
**Only applies to new windows.

Example
-------
>>> settings.loadTheme("classic")
>>> settings.colorCode = (0, 0, 1, 1)
>>> settings.colorStderr
(1, 0, 0, 1)
>>> settings.saveTheme("mine")
>>> settings.availableFonts
Menlo-Regular
MyOwnMono-Regular
>>> settings.fontName = "MyOwnMono-Regular"
>>> settings.fontSize
20
>>> settings.fontSize = 12
""".strip()


class PyREPLSettings(object):

    def __init__(self):
        self._dispatcher = NotificationCenter()

    def __repr__(self):
        return "<Editor Settings Manager. Type \"settings.help\" for documentation.>"

    def _get_help(self):
        # LOL. This is probably very illegal.
        print settingsManagerDoc

    help = property(_get_help)

    # Notifications

    def addObserver(self, obj, methodName, notification="PyREPL.SettingsChanged"):
        self._dispatcher.addObserver(obj, methodName, notification=notification, observable=self)

    def removeObserver(self, obj, notification="PyREPL.SettingsChanged"):
        self._dispatcher.removeObserver(obj, notification, self)

    def postNotification(self, notification="PyREPL.SettingsChanged", data=None):
        self._dispatcher.postNotification(notification, self, data)

    # Properties

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
    showInvisibleCharacters = settingsProperty("showInvisibleCharacters", settingsBoolValidator)

    def editorItems(self):
        d = dict(
            fontName=self.fontName,
            fontSize=self.fontSize,
            colorCode=self.colorCode,
            colorStdout=self.colorStdout,
            colorStderr=self.colorStderr,
            colorBackground=self.colorBackground,
            tabString=self.tabString,
            showInvisibleCharacters=self.showInvisibleCharacters
        )
        return d.items()

    # Fonts

    def _get_availableFonts(self):
        manager = NSFontManager.sharedFontManager()
        for name in manager.availableFonts():
            font = NSFont.fontWithName_size_(name, 10)
            if font.isFixedPitch():
                print name

    availableFonts = property(_get_availableFonts)

    # Startup Code

    def editStartupCode(self):
        self.postNotification(notification="PyREPL.ShowStartupCodeEditor")

    # Themes

    def loadTheme(self, name):
        userThemes = getDefaultValue("userThemes")
        if name in userThemes:
            theme = userThemes[name]
        elif name in defaultThemes:
            theme = defaultThemes[name]
        else:
            raise PyREPLSettingsError("No theme named %r." % name)
        self.colorCode = theme["colorCode"]
        self.colorStdout = theme["colorStdout"]
        self.colorStderr = theme["colorStderr"]
        self.colorBackground = theme["colorBackground"]

    def saveTheme(self, name):
        if not settingsStringValidator(name):
            raise PyREPLSettingsError("Theme names must be strings.")
        theme = dict(
            colorCode=self.colorCode,
            colorStderr=self.colorStderr,
            colorStdout=self.colorStdout,
            colorBackground=self.colorBackground
        )
        userThemes = getDefaultValue("userThemes")
        userThemes[name] = theme
        setDefaultValue("userThemes", userThemes)


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
        if inRoboFont:
            windowClass = vanilla.FloatingWindow
        else:
            windowClass = vanilla.Window
        self.w = windowClass((600, 400), "RoboREPL", minSize=(350, 200))
        self.w.editor = PyREPLTextEditor((0, 0, 0, 0))
        self.loadSettings()
        self.w.editor.startSession(settingsManager.bannerGreeting, settingsManager.startupCode)

        window = self.w.getNSWindow()
        window.setOpaque_(False)
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
            showInvisibleCharacters=self.w.editor.setShowInvisibles
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

        paragraphStyle = NSMutableParagraphStyle.alloc().init()
        paragraphStyle.setLineHeightMultiple_(1.2)
        self.setDefaultParagraphStyle_(paragraphStyle)

        self.setUsesFindBar_(True)

        self.setAutomaticQuoteSubstitutionEnabled_(False)
        self.setAutomaticLinkDetectionEnabled_(False)
        self.setContinuousSpellCheckingEnabled_(False)
        self.setGrammarCheckingEnabled_(False)
        self.setAutomaticDashSubstitutionEnabled_(False)
        self.setAutomaticDataDetectionEnabled_(False)
        self.setAutomaticSpellingCorrectionEnabled_(False)
        self.setAutomaticTextReplacementEnabled_(False)

        self._codeColor = NSColor.blackColor()
        self._stderrColor = NSColor.blackColor()
        self._stdoutColor = NSColor.blackColor()
        self._glyphWidth = 1

        self._console = InteractiveConsole(locals=namespaceInjections)
        self._stderr = PseudoUTF8Output(self.writeStderr_)
        self._stdout = PseudoUTF8Output(self.writeStdout_)
        self._prompt = sys.ps1
        self.previousOutput = ""

        self._tabString = "  "

        self._minInsertionPoint = 0

        self._history = []
        self._historyIndex = 1

        return self

    # Settings

    def setTabString_(self, value):
        self._tabString = value

    def setFont_(self, value):
        super(PyREPLTextView, self).setFont_(value)
        self.getCharacterBox()

    def getCharacterBox(self):
        font = self.font()
        glyph = font.glyphWithName_("space")
        glyphWidth = font.advancementForGlyph_(glyph).width
        glyphHeight = font.pointSize() * self.defaultParagraphStyle().lineHeightMultiple()
        self._glyphWidth = glyphWidth
        self._glyphHeight = glyphHeight
        return glyphWidth, glyphHeight

    def setCodeColor_(self, color):
        self._codeColor = color
        self.setTextColor_(color)
        self.setInsertionPointColor_(color)

    def setStdoutColor_(self, color):
        self._stdoutColor = color

    def setStderrColor_(self, color):
        self._stderrColor = color

    def setShowInvisibles_(self, value):
        self.layoutManager().setShowsInvisibleCharacters_(value)

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
        elif event.modifierFlags() & NSCommandKeyMask and event.characters() == "c":
            pb = NSPasteboard.generalPasteboard()
            pb.clearContents()
            a = NSArray.arrayWithObject_(self.previousOutput)
            pb.writeObjects_(a)
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

    def insertBacktab_(self, sender):
        if self.currentLine().endswith(self._tabString):
            length = len(self._tabString)
            begin = self.textLength() - length
            textStorage = self.textStorage()
            textStorage.deleteCharactersInRange_((begin, length))

    def moveDown_(self, sender):
        self._historyIndex += 1
        if self._historyIndex > len(self._history):
            self._historyIndex = len(self._history)
            NSBeep()
        self._insertHistoryLine()

    def moveUp_(self, sender):
        self._historyIndex -= 1
        if self._historyIndex < 0:
            self._historyIndex = 0
            NSBeep()
        self._insertHistoryLine()

    def _insertHistoryLine(self):
        if self._historyIndex == len(self._history):
            text = ""
        else:
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
            NSFontAttributeName : self.font(),
            NSParagraphStyleAttributeName : self.defaultParagraphStyle()
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
        self._minInsertionPoint = 0
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
        save = (sys.stdout, sys.stderr, self.rawText())
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
            sys.stdout, sys.stderr, previousRawText = save
            self.previousOutput = self.rawText()[len(previousRawText):-1]

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

    def drawInsertionPointInRect_color_turnedOn_(self, rect, color, turnedOn):
        if hasattr(self, "_glyphWidth"):
            rect.size.width = self._glyphWidth
        super(PyREPLTextView, self).drawInsertionPointInRect_color_turnedOn_(rect, color, turnedOn)

    def setNeedsDisplayInRect_(self, rect):
        # Ugh: https://gist.github.com/koenbok/a1b8d942977f69ff102b
        if hasattr(self, "_glyphWidth"):
            rect.size.width += self._glyphWidth - 1
        super(PyREPLTextView, self).setNeedsDisplayInRect_(rect)

    # Auto Completion (adapted from DrawBot)

    def rangeForUserCompletion(self):
        charRange = super(PyREPLTextView, self).rangeForUserCompletion()
        text = self.string()
        partialString = text.substringWithRange_(charRange)
        if "." in partialString:
            dotSplit = partialString.split(".")
            partialString = dotSplit.pop()
            move = len(".".join(dotSplit))
            charRange.location += move + 1
            charRange.length = len(partialString)
        for c in partialString:
            if c not in variableChars:
                return (NSNotFound, 0)
        return charRange

    def completionsForPartialWordRange_indexOfSelectedItem_(self, charRange, index):
        if not haveJedi:
            return [], 0
        text = self.string()
        partialString = text.substringWithRange_(charRange)
        source = "\n".join(self._history + [self.currentLine()])
        namespace = self._console.locals
        script = jedi.Interpreter(source=source, namespaces=[namespace])
        completions = []
        for completion in script.completions():
            name = completion.name
            completions.append(name)
        return completions, 0

    def selectionRangeForProposedRange_granularity_(self, proposedRange, granularity):
        location = proposedRange.location
        if granularity == NSSelectByWord and proposedRange.length == 0 and location != 0:
            text = self.string()
            lenText = len(text)
            length = 1
            found = False
            while not found:
                location -= 1
                length += 1
                if location <= 0:
                    found = True
                else:
                    c = text.substringWithRange_((location, 1))[0]
                    if c not in variableChars:
                        location += 1
                        found = True
            found = False
            while not found:
                length += 1
                if location + length >= lenText:
                    found = True
                else:
                    c = text.substringWithRange_((location, length))[-1]
                    if c not in variableChars:
                        length -= 1
                        found = True
            return location, length
        else:
            return super(PyREPLTextView, self).selectionRangeForProposedRange_granularity_(proposedRange, granularity)

    # Drop

    def readSelectionFromPasteboard_type_(self, pboard, pbType):
        if pbType == NSFilenamesPboardType:
            paths = pboard.propertyListForType_(NSFilenamesPboardType)
            dropText = ""
            if len(paths) == 1:
                dropText = 'u"%s"' % paths[0]
            else:
                formattedPaths = []
                for path in paths:
                    formattedPaths.append('u"%s"' % path)
                dropText = "[%s]" % ", ".join(formattedPaths)
            if dropText:
                self.insertText_(dropText)
                return True
        return super(PyREPLTextView, self).readSelectionFromPasteboard_type_(pboard, pbType)


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

    def setShowInvisibles(self, value):
        self.getNSTextView().setShowInvisibles_(value)

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
