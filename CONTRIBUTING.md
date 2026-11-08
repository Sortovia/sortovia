# Contributing to Sortovia

Thanks for helping. Bug reports, ideas and pull requests are all welcome.

## Reporting a bug

Open an issue with the **Bug report** form. Say which version of Sortovia and Kodi you use, on which device,
and what happened. A Kodi log helps most: **Help > Send a problem report** in Sortovia makes one. Read it
before posting, because file names in the log can show what's in your library.

## Changing the code

Sortovia is plain Python with no outside packages, so it runs anywhere Kodi does.

1. Fork the repository and make a branch.
2. Run the tests: `python -m unittest discover -s tests`. They run without Kodi.
3. Keep to how the add-on already behaves: it shows every move before making it, never overwrites without
   asking, and never deletes a file the person didn't choose.
4. Write messages and labels in plain English for someone who isn't technical.
5. Open a pull request saying what changed and how you tested it.

[DEVELOPMENT.md](DEVELOPMENT.md) explains how the code is laid out and how to build the add-on.

## The name and logo

The code is under the MIT licence. The Sortovia name and logo aren't: see [LICENSE.txt](LICENSE.txt). If you
publish your own version, give it your own name and logo.
