"""关卡数据。
U 上 / D 下 / L 左 / R 右 / . 空位
所有关卡都通过 solve_level 验证存在通关顺序，并由单元测试兜底。
注：设计关卡时必须避免"两个箭头在同一行/列正面对撞"——
那会形成互相阻挡的死锁，关卡无解。
"""

LEVELS = [
    {
        "name": "入门",
        "mistakes": 3,
        "par_time": 25.0,
        "rows": [
            ".U.",
            "R.D",
            ".L.",
        ],
        # 通关顺序：U(0,1) → D(1,2) → L(2,1) → R(1,0)
    },
    {
        "name": "交错",
        "mistakes": 3,
        "par_time": 45.0,
        "rows": [
            "D.RU",
            ".D..",
            "L.U.",
            ".D.L",
        ],
        # 起始可点：U(0,3)、L(2,0)、D(3,1)
        # 三条依赖链：(0,3)U → (0,2)R → (2,2)U
        #             (2,0)L → (0,0)D
        #             (3,1)D → (1,1)D 和 (3,3)L
    },
    {
        "name": "环链",
        "mistakes": 4,
        "par_time": 60.0,
        "rows": [
            "..U..",
            "..U..",
            "LLURR",
            "..D..",
            "..D..",
        ],
        # 四臂结构：外层 4 个箭头全部朝外、开局可点
        # 敲掉外层后，内层 4 个解锁；中心 (2,2) 最晚出
    },
    {
        "name": "深层",
        "mistakes": 3,
        "par_time": 75.0,
        "rows": [
            ".D.R.",
            ".D...",
            "D.L.R",
            "...U.",
            ".D.U.",
        ],
        # 两条深度为 3 的依赖链：
        #   列 1：(4,1)D → (1,1)D → (0,1)D
        #   列 3：(0,3)R → (3,3)U → (4,3)U
        # 另有 (2,0)D → (2,2)L
    },
]


def validate_levels():
    """开发期自检：逐关确认存在通关顺序，并返回每关的步数。"""
    from logic import parse_level, solve_level
    report = []
    for index, level in enumerate(LEVELS, start=1):
        grid = parse_level(level["rows"])
        moves = solve_level(grid)
        if moves is None:
            raise ValueError(f"第 {index} 关（{level['name']}）无解，请重新设计")
        total = sum(1 for line in grid for value in line if value)
        if len(moves) != total:
            raise ValueError(f"第 {index} 关解法步数与箭头数不一致")
        report.append((index, level["name"], total, len(moves)))
    return report


if __name__ == "__main__":
    for idx, name, total, steps in validate_levels():
        print(f"第 {idx} 关 {name}：{total} 个箭头，{steps} 步解法，校验通过")
