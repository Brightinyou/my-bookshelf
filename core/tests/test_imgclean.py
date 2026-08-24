# -*- coding: utf-8 -*-
"""밑줄 제거 회귀 테스트 — services/imgclean.

이 장치의 존재 이유: 독자가 그어 둔 밑줄이 글자 밑변에 붙어 판독을 망친다. 실측
(『기술신학』 30쪽, Apple Vision) 오독 16곳 → 4곳, 유사도 0.974 → 0.995.

★**절반은 '안 바꾸는 것'을 지킨다.** 밑줄 없는 쪽을 건드리면 멀쩡한 판독이 나빠진다
(실측 45쪽: 지운 화소 42개, 판독 결과 완전 동일). 이진화도 하지 않는다 — 적응
이진화를 넣었더니 유사도가 0.928로 떨어지고 `벽돌이`를 통째로 잃었다.
"""
import unittest

try:
    import numpy as np
    from services import imgclean
except Exception:                                  # numpy 없는 환경에서는 건너뛴다
    np = None


@unittest.skipIf(np is None, "numpy 없음")
class ImgCleanTest(unittest.TestCase):
    def _page(self, h=200, w=400):
        """흰 바탕에 20px 높이의 글자 줄 셋을 흉내 낸 쪽."""
        img = np.full((h, w, 3), 255, np.uint8)
        for y in (30, 80, 130):
            for x in range(20, 380, 25):
                img[y:y + 20, x:x + 14] = 40       # 글자 덩어리
        return img

    def test_밑줄을_지운다(self):
        img = self._page()
        img[52:54, 20:380] = 30                    # 첫 줄 아래 긴 밑줄
        out, erased, _ = imgclean.strip_underlines(img)
        self.assertGreater(erased, 200)
        self.assertGreater(out[52:54, 200:300].mean(), 200)   # 밑줄 자리가 희어졌다

    def test_밑줄이_없으면_아무것도_안_한다(self):
        img = self._page()
        out, erased, _ = imgclean.strip_underlines(img)
        self.assertEqual(erased, 0)
        self.assertTrue((out == img[:, :, 1]).all())

    def test_글자는_남긴다(self):
        img = self._page()
        img[52:54, 20:380] = 30
        before = (img[:, :, 1] < 128).sum()
        out, _, _ = imgclean.strip_underlines(img)
        after = (out < 128).sum()
        # 밑줄(약 720화소)만 없어지고 글자는 거의 그대로여야 한다
        self.assertGreater(after, before * 0.85)

    def test_이진화하지_않는다(self):
        """회색조를 그대로 두고 흰색만 칠한다 — 이진화는 실측상 해로웠다."""
        img = self._page()
        img[60:70, 100:120] = 150                  # 중간 밝기 얼룩
        out, _, _ = imgclean.strip_underlines(img)
        self.assertIn(150, np.unique(out))

    def test_글자_높이를_잰다(self):
        """책마다 다르므로 고정값을 쓰면 안 된다."""
        img = self._page()
        _, _, ch = imgclean.strip_underlines(img)
        self.assertEqual(ch, 20)


if __name__ == "__main__":
    unittest.main()
