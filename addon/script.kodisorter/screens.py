"""Full-window pages and a guide reader that scrolls slowly, one line at a time.

Kodi's own dialogs are small and page through text. These windows are built from Kodi's
standard controls, and anything that goes wrong falls back to Kodi's own dialog.
"""
import re

MEDIA = "special://home/addons/script.kodisorter/resources/media/"
LONG = 110          # messages longer than this get the full window
BACK = (9, 10, 13, 92)
LEFT, RIGHT, UP, DOWN, PAGE_UP, PAGE_DOWN = 1, 2, 3, 4, 5, 6
SELECT, PAUSE, PLAY = 7, 12, 79
CHARS_PER_LINE = 100
ROWS = 19


def line_count(text, width=CHARS_PER_LINE):
    """How many lines the text fills on screen (an estimate: Kodi does the real wrapping)."""
    plain = re.sub(r"\[/?[A-Z]+[^\]]*\]", "", text or "")
    return sum(max(1, (len(l) + width - 1) // width) for l in plain.split("\n"))


class Scroller(object):
    """Where the reader is, one line at a time, so no line is skipped between pages."""
    SLOWEST, FASTEST, STEP = 8.0, 1.0, 0.5

    def __init__(self, lines, rows=ROWS, delay=3.5, hold=5.0, now=0.0):
        self.last = max(0, lines - rows)
        self.pos = 0
        self.delay = delay
        self.playing = self.last > 0
        self.due = now + hold

    def tick(self, now):
        """True if it moved on a line."""
        if not self.playing or now < self.due:
            return False
        if self.pos >= self.last:
            self.playing = False
            return False
        self.pos += 1
        self.due = now + self.delay
        return True

    def move(self, lines, now):
        """Arrow keys: go by hand. Moving by hand pauses the scrolling."""
        self.playing = False
        self.pos = min(self.last, max(0, self.pos + lines))

    def toggle(self, now):
        self.playing = not self.playing and self.pos < self.last
        self.due = now + 1.0

    def slower(self):
        self.delay = min(self.SLOWEST, self.delay + self.STEP)

    def faster(self):
        self.delay = max(self.FASTEST, self.delay - self.STEP)

    def hint(self):
        state = "Scrolling" if self.playing else "Paused"
        return "%s, %.1f s per line.   OK: pause or play    Up/Down: move    Left/Right: slower/faster    Back: close" % (
            state, self.delay)


def show_page(title, body, buttons):
    """A full-window message. Returns the button pressed, or -1 for Back."""
    import xbmcgui

    class Page(xbmcgui.WindowDialog):
        choice = -1
        ids = []

        def onAction(self, action):
            if action.getId() in BACK:
                self.close()

        def onControl(self, control):
            cid = control.getId()
            if cid in self.ids:
                self.choice = self.ids.index(cid)
                self.close()

    win = Page()
    win.addControl(xbmcgui.ControlImage(0, 0, 1280, 720, MEDIA + "panel.png"))
    win.addControl(xbmcgui.ControlImage(1140, 24, 80, 80, MEDIA + "logo.png"))
    win.addControl(xbmcgui.ControlLabel(60, 40, 1060, 44, "[B]%s[/B]" % title, font="font13", textColor="FF2EC4B6"))
    box = xbmcgui.ControlTextBox(60, 116, 1160, 484, font="font13", textColor="FFFFFFFF")
    win.addControl(box)
    box.setText(body)
    width = 300
    x = 60
    made = []
    for label in buttons:
        b = xbmcgui.ControlButton(x, 620, width, 60, label, focusTexture=MEDIA + "focus.png",
                                  noFocusTexture=MEDIA + "button.png", alignment=6, font="font13",
                                  textColor="FFFFFFFF", focusedColor="FF0F1A24")
        win.addControl(b)
        made.append(b)
        x += width + 30
    for i, b in enumerate(made):
        b.setNavigation(b, b, made[i - 1], made[(i + 1) % len(made)])
    win.ids = [b.getId() for b in made]
    win.setFocus(made[-1])
    win.doModal()
    choice = win.choice
    del win
    return choice


def read_text(title, text):
    """Show text in the reader until Back is pressed."""
    import time
    import xbmc
    import xbmcgui

    state = Scroller(line_count(text), now=time.time())

    class Reader(xbmcgui.WindowDialog):
        closed = False

        def onAction(self, action):
            a, now = action.getId(), time.time()
            if a in BACK:
                self.closed = True
            elif a in (SELECT, PAUSE, PLAY):
                state.toggle(now)
            elif a == UP:
                state.move(-1, now)
            elif a == DOWN:
                state.move(1, now)
            elif a == PAGE_UP:
                state.move(-(ROWS - 2), now)
            elif a == PAGE_DOWN:
                state.move(ROWS - 2, now)
            elif a == LEFT:
                state.slower()
            elif a == RIGHT:
                state.faster()

    win = Reader()
    win.addControl(xbmcgui.ControlImage(0, 0, 1280, 720, MEDIA + "panel.png"))
    win.addControl(xbmcgui.ControlLabel(40, 18, 1200, 40, "[B]%s[/B]" % title, font="font13", textColor="FF2EC4B6"))
    box = xbmcgui.ControlTextBox(40, 66, 1200, 600, font="font13", textColor="FFFFFFFF")
    win.addControl(box)
    box.setText(text)
    hint = xbmcgui.ControlLabel(40, 676, 1200, 34, state.hint(), font="font12", textColor="FFA9BAC0")
    win.addControl(hint)
    monitor = xbmc.Monitor()
    win.show()
    try:
        shown_pos, shown_hint = 0, state.hint()
        while not win.closed and not monitor.abortRequested():
            state.tick(time.time())
            if state.pos != shown_pos:
                shown_pos = state.pos
                box.scroll(shown_pos)
            if state.hint() != shown_hint:
                shown_hint = state.hint()
                hint.setLabel(shown_hint)
            if monitor.waitForAbort(0.1):
                break
    finally:
        win.close()
        del win


class Friendly(object):
    """Kodi's dialog, with long messages in a full window and text in the reader."""
    def __init__(self, dlg):
        self.dlg = dlg

    def __getattr__(self, name):
        return getattr(self.dlg, name)

    def ok(self, heading, message):
        if len(message) > LONG:
            try:
                show_page(heading, message, ["OK"])
                return True
            except Exception:
                pass
        return self.dlg.ok(heading, message)

    def yesno(self, heading, message, nolabel="No", yeslabel="Yes", **kw):
        if len(message) > LONG:
            try:
                return show_page(heading, message, [nolabel, yeslabel]) == 1
            except Exception:
                pass
        return self.dlg.yesno(heading, message, nolabel=nolabel, yeslabel=yeslabel, **kw)

    def textviewer(self, heading, text, *a, **k):
        try:
            return read_text(heading, text)
        except Exception:
            return self.dlg.textviewer(heading, text, *a, **k)
