import re
from langdetect import detect
from collections import Counter

# 嘗試不同偏移值
def guess_offset(cid_text, range_start=19100, range_end=20000):
    cids = re.findall(r'\(cid:(\d+)\)', cid_text)
    cids = [int(cid) for cid in cids]

    scores = {}
    for offset in range(range_start, range_end):
        try:
            decoded = ''.join(chr(cid + offset) for cid in cids)
            lang = detect(decoded)
            if lang == 'zh-cn' or lang == 'zh-tw':
                scores[offset] = scores.get(offset, 0) + 1
        except:
            continue

    if not scores:
        print("❌ 無法推斷有效偏移")
        return None

    most_common = Counter(scores).most_common(1)[0][0]
    print(f"✅ 最佳偏移值為: {most_common}")
    return most_common

# 🧪 使用方法
if __name__ == "__main__":
    test_text = """
        (cid:17836)
01
CAPITAL │ 2023 AUUNAL REPORT
(cid:3)
(cid:25026)
(cid:3)(cid:38)(cid:82)(cid:81)(cid:87)(cid:72)(cid:81)(cid:87)(cid:86)(cid:3)
(cid:19)(cid:19)(cid:21)(cid:3) (cid:10167)(cid:433)(cid:20658)(cid:20319)(cid:13871)(cid:9967)(cid:8968)(cid:13750)(cid:3)(cid:3)(cid:3)(cid:3)
(cid:19)(cid:19)(cid:27)(cid:3) (cid:23409)(cid:433)(cid:8234)(cid:8886)(cid:19167)(cid:7561)(cid:3)(cid:3)(cid:3)(cid:3)(cid:3)(cid:3)(cid:3)(cid:3)
    """
    guess_offset(test_text)