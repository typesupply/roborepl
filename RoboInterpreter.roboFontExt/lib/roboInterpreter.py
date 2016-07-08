"""
- rf namespace
- cursor drawing
- line spacing

- set font
- set color

- RF code key commands
- completion
"""

# This was inspired by the PyObjC PyInterpreter demo.

import sys
from code import InteractiveConsole
from AppKit import *
import vanilla
from vanilla.vanillaTextEditor import VanillaTextEditorDelegate

try:
    sys.ps1
except AttributeError:
    sys.ps1 = ">>> "
try:
    sys.ps2
except AttributeError:
    sys.ps2 = "... "

try:
    from mojo import roboFont
    locals = {
        "AllFonts" : roboFont.AllFonts,
        "CurrentFont" : roboFont.CurrentFont,
        "CurrentGlyph" : roboFont.CurrentGlyph,
        "OpenFont" : roboFont.OpenFont,
        "NewFont" : roboFont.NewFont,
    }
except ImportError:
    locals = {}


class PyInterpreterWindow(object):

    def __init__(self):
        editor = PyInterpreterTextEditor((0, 0, 0, 0))
        w, h = editor.getNSTextView().getConsoleSize()

        self.w = vanilla.Window((w + 10, h + 10))
        self.w.editor = editor

        window = self.w.getNSWindow()
        window.setBackgroundColor_(NSColor.clearColor())

        self.w.open()


# ------
# Editor
# ------

class PyInterpreterTextView(NSTextView):

    def init(self):
        self = super(PyInterpreterTextView, self).init()
        self.setDelegate_(self)

        self.setDrawsBackground_(True)
        self.setFont_(NSFont.userFixedPitchFontOfSize_(20))
        self.setCodeColor_(NSColor.colorWithCalibratedRed_green_blue_alpha_(0, 1, 0, 1))
        self.setStdoutColor_(NSColor.colorWithCalibratedRed_green_blue_alpha_(1, 1, 1, 1))
        self.setStderrColor_(NSColor.colorWithCalibratedRed_green_blue_alpha_(1, 0, 0, 1))
        self.setBackgroundColor_(NSColor.colorWithCalibratedRed_green_blue_alpha_(0, 0, 0, 0.9))
        self._editorParagraphStyle = NSMutableParagraphStyle.alloc().init()

        self._console = InteractiveConsole(locals=locals)
        self._stderr = PseudoUTF8Output(self.writeStderr_)
        self._stdout = PseudoUTF8Output(self.writeStdout_)
        self._prompt = sys.ps1

        self._minInsertionPoint = 0

        self._history = [""]
        self._historyIndex = 1

        return self

    def getConsoleSize(self):
        columnCount = 80
        rowCount = 24
        width = self._glyphWidth * columnCount
        height = self._lineHeight * rowCount
        return (width, height)

    # Settings

    def setFont_(self, font):
        glyph = font.glyphWithName_("space")
        self._glyphWidth = font.advancementForGlyph_(glyph).width
        self._lineHeight = font.pointSize() + font.leading()
        return super(PyInterpreterTextView, self).setFont_(font)

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
            return super(PyInterpreterTextView, self).keyDown_(event)

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

    def currentLine(self):
        line = self.rawText().splitlines()[-1]
        line = line[len(self._prompt):]
        return line

    def executeLine_(self, line):
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


class PyInterpreterTextEditor(vanilla.TextEditor):

    nsTextViewClass = PyInterpreterTextView

    def __init__(self, *args, **kwargs):
        super(PyInterpreterTextEditor, self).__init__(*args, **kwargs)
        textView = self.getNSTextView()
        textView.writePrompt()
        scrollView = self.getNSScrollView()
        scrollView.setDrawsBackground_(False)
        scrollView.setBorderType_(NSNoBorder)


# -------------------
# Interpreter Support
# -------------------

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
    executeVanillaTest(PyInterpreterWindow)
