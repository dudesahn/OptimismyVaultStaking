import brownie
from brownie import ZERO_ADDRESS, chain, interface
import pytest

# this shows that our new zap, when deployed and used with existing pool contracts, works great
def test_new_zap_works(
    gov,
    yvdai,
    yvdai_amount,
    yvdai_whale,
    dai,
    dai_amount,
    dai_whale,
    yvusdc,
    yvusdc_amount,
    yvusdc_whale,
    yvop,
    yvop_whale,
    registry,
    new_zap,
    yvdai_pool,
    yvusdc_pool,
    RELATIVE_APPROX,
):
    # Approve and zap into to the staking contract
    dai_starting = dai.balanceOf(dai_whale)
    dai.approve(new_zap, 2**256 - 1, {"from": dai_whale})

    # oChad lowers deposit yvdai, fucking rude!
    yvdai.setDepositLimit(yvdai.totalAssets() + 100e18, {"from": gov})

    # update our zap contract
    yvdai_pool.setZapContract(new_zap, {"from": gov})

    # zap in, but it should fail
    with brownie.reverts():
        new_zap.zapIn(yvdai, dai_amount, {"from": dai_whale})
    assert dai.balanceOf(dai_whale) == dai_starting
    assert dai.balanceOf(new_zap) == 0
