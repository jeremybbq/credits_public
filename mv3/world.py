# The one continuous take: a world that steps forward 60 times a second and hands each material to the next.
from core import BLACK, DT, Ctx, section_at
from term import Screen

_REG = {}


def material(name):
    def deco(cls):
        _REG[name] = cls
        return cls
    return deco


class Material:
    def __init__(self, prev, ctx):
        pass

    def step(self, ctx):
        pass

    def draw(self, s, ctx):
        pass


def _load():
    if not _REG:
        import m_early  # noqa: F401
        import m_mid    # noqa: F401
        import m_late   # noqa: F401
    return _REG


class World:
    def __init__(self, audio):
        _load()
        self.audio = audio
        self.t = -DT
        self.name = None
        self.mat = None
        self.ctx = None

    def advance(self, t):
        ctx = Ctx(t, self.audio, self.t)
        name = section_at(ctx.b)
        if name != self.name:
            self.mat = _REG[name](self.mat, ctx)
            self.name = name
        self.mat.step(ctx)
        self.t = t
        self.ctx = ctx

    def draw(self):
        s = Screen(bg=BLACK)
        self.mat.draw(s, self.ctx)
        return s
