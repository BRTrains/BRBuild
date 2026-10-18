from PropertyCalculation.DoorType import DoorType
from PropertyCalculation.LoadingSpeed import loading_speed_for
from PropertyCalculation.TrainType import TrainType
from PropertyCalculation.VehicleUsage import VehicleUsage


def test_loading_speed_order_matches_door_access():
    assert [
        loading_speed_for(doors=door)
        for door in (
            DoorType.INTERCITY,
            DoorType.COMMUTER_DOUBLE,
            DoorType.COMMUTER_TRIPLE,
            DoorType.MULTIPLE,
        )
    ] == [10, 20, 25, 30]


def test_slam_doors_reduce_the_inferred_speed_by_one_third():
    assert loading_speed_for(doors=DoorType.SLAM, usage=VehicleUsage.INTERCITY) == 6
    assert loading_speed_for(doors=DoorType.SLAM, usage=VehicleUsage.COMMUTER) == 13


def test_missing_doors_are_inferred_from_usage():
    assert loading_speed_for(usage=VehicleUsage.INTERCITY) == 10
    assert loading_speed_for(usage=VehicleUsage.COMMUTER) == 20


def test_missing_usage_uses_speed_fallback():
    assert loading_speed_for(speed=101) == 10
    assert loading_speed_for(speed=100) == 20


def test_coach_without_speed_or_usage_defaults_to_intercity():
    assert loading_speed_for(train_type=TrainType.COACH) == 10


def test_no_passenger_signal_does_not_change_freight_defaults():
    assert loading_speed_for(train_type=TrainType.WAGON) is None
