"""The optional quote line: a Marcus Aurelius line chosen by, and colored to, the 5-hour load.

The text follows the public-domain George Long translation (1862), modernized.
Tiers climb with the load: start, center, strive, endure.
"""

from pace import project

ROTATE_SECONDS = 120

MEDITATIONS = (
    (
        "Confine yourself to the present.",
        "Do every act as if it were your last.",
        "No longer talk of what a good man should be. Be one.",
        "Death hangs over you; while you can, be good.",
        "Do not act as if you had ten thousand years to live.",
        "Whatever you do, do it as one who may depart at any moment.",
        "Remember how long you have put these things off.",
        "You may leave life this moment; let that govern what you do.",
        "The time any man lives is but a little.",
        "Let no act be done without purpose.",
    ),
    (
        "Nowhere can a man retreat better than into his own soul.",
        "Look within; within is the fountain of good.",
        "Whenever you wish, you can retire into yourself and be at rest.",
        "The soul is dyed by its thoughts.",
        "Very little is needed to make a happy life.",
        "Tranquility is nothing but the good ordering of the mind.",
        "Be cheerful, and need no one's help.",
        "Keep yourself pure from passion, rashness, and vanity.",
        "Be never in haste, and never slow.",
        "What suits you, O Universe, suits me.",
    ),
    (
        "Always take the short road; the short road is nature's.",
        "If it is not right, do not do it; if it is not true, do not say it.",
        "The art of living is more like wrestling than dancing.",
        "Do nothing at random, but by the exact rules of the art.",
        "Do what you are about with gravity, freedom, and justice.",
        "The best revenge is not to become like your enemy.",
        "A happy lot: good inclinations, good desires, good actions.",
        "Does a man offend? It is against himself that he offends.",
        "The obstacle on the road becomes the road.",
        "Take refuge in work, and be at rest.",
    ),
    (
        "Be like the headland the waves break on; it stands, the sea falls still.",
        "Nothing happens to anyone that he is not formed by nature to bear.",
        "Whatever happens in the world happens justly.",
        "Take away the opinion, and the hurt is gone.",
        "Nothing that is according to nature can be evil.",
        "The universe is change; life is what our thoughts make it.",
        "You have boarded, you have sailed, you have reached the shore. Step off.",
        "In a little while you and he will both be dead.",
        "Consider how quickly all things dissolve into the whole.",
        "Time is a river of passing events; strong is its current.",
    ),
)



def tier(proj):
    """The quote tier for a projected load: 0 under 50, 1 under 70, 2 under 90, else 3."""
    if proj is None:
        return None
    return 3 if proj >= 90 else 2 if proj >= 70 else 1 if proj >= 50 else 0


def line(theme, window, now, color_for):
    """The quote line for the 5-hour window, or None when its projection is unknown."""
    if window is None:
        return None
    proj = project(window.used, window.resets_at, window.seconds, now)
    level = tier(proj)
    if level is None:
        return None
    pool = MEDITATIONS[level]
    quote = pool[(int(now) // ROTATE_SECONDS) % len(pool)]
    return "%s%sTo Himself%s%s%s: %s%s%s" % (
        color_for(theme, proj), theme.italic, theme.reset,
        theme.dim, theme.italic, quote, theme.no_italic, theme.reset)
