"""조회 결과의 완전성을 검사한다.

부분 성공을 만들지 않는다. 반쪽 알림은 읽는 사람이 빠진 것을 알아차리기 어렵다.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def ensure_complete(fetched: Mapping[str, float | None], required: Sequence[str]) -> dict[str, float]:
    """요청한 티커가 모두 값을 가졌는지 확인한다.

    하나라도 빠지면 전체를 실패로 돌린다. 값이 없을 때 앞 값이나 평균으로 채우지 않는다.

    Args:
        fetched: 조회 결과. 값이 없으면 None.
        required: 있어야 하는 티커.

    Returns:
        요청한 티커만 담은 결과.

    Raises:
        ValueError: 요청한 티커가 결과에 없거나 값이 비어 있을 때.
    """
    missing = [ticker for ticker in required if fetched.get(ticker) is None]
    if missing:
        raise ValueError(f"시세를 받지 못한 종목이 있습니다: {', '.join(missing)}. 조회를 다시 실행하세요.")

    complete: dict[str, float] = {}
    for ticker in required:
        value = fetched[ticker]
        if value is None:
            raise RuntimeError(f"내부 불변조건 위반: 결측 검사를 통과한 {ticker} 의 값이 비어 있습니다.")
        complete[ticker] = float(value)
    return complete
