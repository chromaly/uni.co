import math


def subtract(a, b):
    return (
        a.x - b.x,
        a.y - b.y,
        a.z - b.z
    )


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def unit(vector):
    length = math.sqrt(dot(vector, vector))

    if length < 0.0001:
        return None

    return tuple(value / length for value in vector)

def measure_finger_tilt(hand):
    if hand is None:
        return None

    bends = []

    for base, joint, next_joint in (
        (5, 6, 7),     # Index finger
        (9, 10, 11),  # Middle finger
    ):
        first_segment = unit(
            subtract(hand[joint], hand[base])
        )
        second_segment = unit(
            subtract(hand[next_joint], hand[joint])
        )

        if first_segment is None or second_segment is None:
            return None

        cosine = dot(first_segment, second_segment)
        cosine = max(-1.0, min(1.0, cosine))

        bends.append(math.degrees(math.acos(cosine)))

    return sum(bends) / len(bends)