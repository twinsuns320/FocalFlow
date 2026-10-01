# FocalFlow

## Windows
[Download for Windows](https://github.com/twinsuns320/FocalFlow/releases/latest/download/FocalFlow_windows.zip)

## Mac
Open Terminal, paste this, and press Enter:

```
cd ~/Downloads && \
curl -fL "https://github.com/twinsuns320/FocalFlow/releases/latest/download/FocalFlow_$(uname -m).zip" -o FocalFlow.zip && \
rm -rf FocalFlow _ff_tmp && mkdir -p _ff_tmp && \
(ditto -x -k FocalFlow.zip _ff_tmp || unzip -q -o FocalFlow.zip -d _ff_tmp) && \
rm FocalFlow.zip && \
entries=(_ff_tmp/*) && \
if [ "${#entries[@]}" -eq 1 ] && [ -d "${entries[0]}" ]; then mv "${entries[0]}" FocalFlow && rmdir _ff_tmp; else mv _ff_tmp FocalFlow; fi && \
open FocalFlow
```

## Free Trial
No key needed to try it. When FocalFlow asks for a key, enter `FreeTrial`. You can upgrade later by entering a purchased key.
