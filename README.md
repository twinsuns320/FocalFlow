# FocalFlow

## Windows
[Download for Windows](https://github.com/twinsuns320/FocalFlow/releases/latest/download/FocalFlow_windows.zip)

## Mac
Open Terminal, paste this, and press Enter:

```
cd ~/Downloads && curl -fL "https://github.com/twinsuns320/FocalFlow/releases/latest/download/FocalFlow_$(uname -m).zip" -o FocalFlow.zip && rm -rf FocalFlow && ditto -x -k FocalFlow.zip /tmp/ff_$$ 2>/dev/null || unzip -q -o FocalFlow.zip -d /tmp/ff_$$; rm FocalFlow.zip && mv "$(find /tmp/ff_$$ -mindepth 1 -maxdepth 1)" FocalFlow && rm -rf /tmp/ff_$$ && open FocalFlow

```

## Free Trial
No key needed to try it. When FocalFlow asks for a key, enter `FreeTrial`. You can upgrade later by entering a purchased key.
