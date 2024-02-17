import brownie
from brownie import ZERO_ADDRESS, chain, interface
import pytest

# things to add: test that the view amounts are correct. test user claims for multiple tokens. test zap out.

# this test asserts that a newly deployed zap with a newly deployed registry works as expected
def test_basic_operation(
    gov,
    yvdai,
    yvdai_amount,
    yvdai_whale,
    yvmkusd,
    yvmkusd_amount,
    yvmkusd_whale,
    ajna,
    ajna_amount,
    ajna_whale,
    registry,
    zap,
    yvdai_pool,
    yvmkusd_pool,
    dai,
):
    # Approve and deposit to the staking contract
    yvdai_starting = yvdai.balanceOf(yvdai_whale)
    yvdai.approve(yvdai_pool, 2**256 - 1, {"from": yvdai_whale})
    yvdai_pool.stake(yvdai_amount, {"from": yvdai_whale})
    assert yvdai_pool.balanceOf(yvdai_whale) == yvdai_amount

    # can't stake zero
    with brownie.reverts("Must be >0"):
        yvdai_pool.stake(0, {"from": yvdai_whale})

    # whale notifies rewards, but only after gov adds token and whale as rewards distro
    # will revert if tried before token is added
    with brownie.reverts():
        yvdai_pool.notifyRewardAmount(ajna, ajna_amount, {"from": ajna_whale})

    # add ajna and grant role to whale
    week = 7 * 86400
    yvdai_pool.addReward(ajna, ajna_whale, week, {"from": gov})

    # now we should be able to notify (make sure we've already done approvals though!)
    before = ajna.balanceOf(ajna_whale)
    ajna.approve(yvdai_pool, 2**256 - 1, {"from": ajna_whale})
    yvdai_pool.notifyRewardAmount(ajna, ajna_amount, {"from": ajna_whale})
    assert before == ajna.balanceOf(ajna_whale) + ajna_amount

    # sleep to gain some earnings
    chain.sleep(86400)
    chain.mine(1)

    # check claimable earnings, get reward
    assert yvdai_pool.getRewardForDuration(ajna) > 0
    earned = yvdai_pool.earned(yvdai_whale, ajna)
    assert earned > 0
    yvdai_pool.getReward({"from": yvdai_whale})
    assert ajna.balanceOf(yvdai_whale) >= earned

    # sleep to gain some earnings
    chain.sleep(86400)
    chain.mine(1)

    # can't withdraw zero
    with brownie.reverts("Must be >0"):
        yvdai_pool.withdraw(0, {"from": yvdai_whale})

    # exit, check that we have the same principal and earned more rewards
    yvdai_pool.exit({"from": yvdai_whale})
    assert yvdai_starting == yvdai.balanceOf(yvdai_whale)
    assert ajna.balanceOf(yvdai_whale) > earned

    # check our setters
    with brownie.reverts("Rewards active"):
        yvdai_pool.setRewardsDuration(ajna, 100e18, {"from": ajna_whale})
    with brownie.reverts("No zero address"):
        yvdai_pool.setZapContract(ZERO_ADDRESS, {"from": gov})
    yvdai_pool.setZapContract(zap, {"from": gov})

    # sleep to get past our rewards window
    chain.sleep(86400 * 6)
    with brownie.reverts("Must be >0"):
        yvdai_pool.setRewardsDuration(ajna, 0, {"from": ajna_whale})
    with brownie.reverts("!authorized"):
        yvdai_pool.setRewardsDuration(ajna, 100e18, {"from": gov})
    yvdai_pool.setRewardsDuration(ajna, 86400 * 14, {"from": ajna_whale})
    assert dai.balanceOf(zap) == 0

    # do a bit more setter testing

    # rewards distro
    with brownie.reverts("No zero address"):
        yvdai_pool.setRewardsDistributor(ZERO_ADDRESS, gov, {"from": gov})
    with brownie.reverts("No zero address"):
        yvdai_pool.setRewardsDistributor(ajna, ZERO_ADDRESS, {"from": gov})
    with brownie.reverts("!authorized"):
        yvdai_pool.setRewardsDistributor(ajna, gov, {"from": ajna_whale})
    yvdai_pool.setRewardsDistributor(ajna, gov, {"from": gov})
    assert yvdai_pool.rewardData(ajna)["rewardsDistributor"] == gov.address

    # ownership
    assert yvdai_pool.pendingOwner() == ZERO_ADDRESS
    with brownie.reverts("!authorized"):
        yvdai_pool.setPendingOwner(ajna_whale, {"from": ajna_whale})
    yvdai_pool.setPendingOwner(ajna_whale, {"from": gov})
    assert yvdai_pool.pendingOwner() == ajna_whale.address
    assert yvdai_pool.owner() == gov.address
    with brownie.reverts("!authorized"):
        yvdai_pool.acceptOwner({"from": gov})
    yvdai_pool.acceptOwner({"from": ajna_whale})
    assert yvdai_pool.owner() == ajna_whale.address
    assert yvdai_pool.pendingOwner() == ZERO_ADDRESS


def test_cloning(
    gov,
    yvdai,
    yvdai_amount,
    yvdai_whale,
    yvmkusd,
    yvmkusd_amount,
    yvmkusd_whale,
    ajna,
    ajna_amount,
    ajna_whale,
    registry,
    zap,
    yvdai_pool,
    yvmkusd_pool,
    dai,
    StakingRewardsMulti,
):

    # Shouldn't be able to call initialize again
    with brownie.reverts():
        yvdai_pool.initialize(
            gov.address,
            yvdai.address,
            zap.address,
            {"from": gov},
        )
    tx = yvdai_pool.cloneStakingPool(
        gov.address,
        yvdai.address,
        zap.address,
        {"from": gov},
    )

    new_staking_pool = StakingRewardsMulti.at(tx.return_value)

    # Shouldn't be able to call initialize again
    with brownie.reverts():
        new_staking_pool.initialize(
            gov.address,
            yvdai.address,
            zap.address,
            {"from": gov},
        )

    ## shouldn't be able to clone a clone
    with brownie.reverts():
        new_staking_pool.cloneStakingPool(
            gov.address,
            yvdai.address,
            zap.address,
            {"from": gov},
        )

    # check owner is correct
    assert new_staking_pool.owner() == gov.address

    # Approve and deposit to the staking contract
    yvdai_starting = yvdai.balanceOf(yvdai_whale)
    yvdai.approve(yvdai_pool, 2**256 - 1, {"from": yvdai_whale})
    yvdai_pool.stake(yvdai_amount, {"from": yvdai_whale})
    assert yvdai_pool.balanceOf(yvdai_whale) == yvdai_amount

    # can't stake zero
    with brownie.reverts("Must be >0"):
        yvdai_pool.stake(0, {"from": yvdai_whale})

    # whale notifies rewards, but only after gov adds token and whale as rewards distro
    # will revert if tried before token is added
    with brownie.reverts():
        yvdai_pool.notifyRewardAmount(ajna, ajna_amount, {"from": ajna_whale})

    # add ajna and grant role to whale
    week = 7 * 86400
    yvdai_pool.addReward(ajna, ajna_whale, week, {"from": gov})

    # now we should be able to notify (make sure we've already done approvals though!)
    before = ajna.balanceOf(ajna_whale)
    ajna.approve(yvdai_pool, 2**256 - 1, {"from": ajna_whale})
    yvdai_pool.notifyRewardAmount(ajna, ajna_amount, {"from": ajna_whale})
    assert before == ajna.balanceOf(ajna_whale) + ajna_amount

    # sleep to gain some earnings
    chain.sleep(86400)
    chain.mine(1)

    # check claimable earnings, get reward
    assert yvdai_pool.getRewardForDuration(ajna) > 0
    earned = yvdai_pool.earned(yvdai_whale, ajna)
    assert earned > 0
    yvdai_pool.getReward({"from": yvdai_whale})
    assert ajna.balanceOf(yvdai_whale) >= earned

    # sleep to gain some earnings
    chain.sleep(86400)
    chain.mine(1)

    # can't withdraw zero
    with brownie.reverts("Must be >0"):
        yvdai_pool.withdraw(0, {"from": yvdai_whale})

    # exit, check that we have the same principal and earned more rewards
    yvdai_pool.exit({"from": yvdai_whale})
    assert yvdai_starting == yvdai.balanceOf(yvdai_whale)
    assert ajna.balanceOf(yvdai_whale) > earned

    # check our setters
    with brownie.reverts("Rewards active"):
        yvdai_pool.setRewardsDuration(ajna, 100e18, {"from": ajna_whale})
    with brownie.reverts("No zero address"):
        yvdai_pool.setZapContract(ZERO_ADDRESS, {"from": gov})
    yvdai_pool.setZapContract(zap, {"from": gov})

    # sleep to get past our rewards window
    chain.sleep(86400 * 6)
    with brownie.reverts("Must be >0"):
        yvdai_pool.setRewardsDuration(ajna, 0, {"from": ajna_whale})
    with brownie.reverts("!authorized"):
        yvdai_pool.setRewardsDuration(ajna, 100e18, {"from": gov})
    yvdai_pool.setRewardsDuration(ajna, 86400 * 14, {"from": ajna_whale})
    assert dai.balanceOf(zap) == 0


def test_multiple_rewards(
    gov,
    yvdai,
    yvdai_amount,
    yvdai_whale,
    yvmkusd,
    yvmkusd_amount,
    yvmkusd_whale,
    ajna,
    ajna_amount,
    ajna_whale,
    prisma,
    prisma_amount,
    prisma_whale,
    registry,
    zap,
    yvdai_pool,
    yvmkusd_pool,
    dai,
):
    # Approve and deposit to the staking contract
    yvdai_starting = yvdai.balanceOf(yvdai_whale)
    yvdai.approve(yvdai_pool, 2**256 - 1, {"from": yvdai_whale})
    yvdai_pool.stake(yvdai_amount, {"from": yvdai_whale})
    assert yvdai_pool.balanceOf(yvdai_whale) == yvdai_amount

    # can't stake zero
    with brownie.reverts("Must be >0"):
        yvdai_pool.stake(0, {"from": yvdai_whale})

    # whale notifies rewards, but only after gov adds token and whale as rewards distro
    # will revert if tried before token is added
    with brownie.reverts():
        yvdai_pool.notifyRewardAmount(ajna, ajna_amount, {"from": ajna_whale})
    with brownie.reverts():
        yvdai_pool.notifyRewardAmount(prisma, prisma_amount, {"from": prisma_whale})

    # add ajna and prisma and grant role to whales
    week = 7 * 86400
    yvdai_pool.addReward(ajna, ajna_whale, week, {"from": gov})
    yvdai_pool.addReward(prisma, prisma_whale, week, {"from": gov})

    # now we should be able to notify (make sure we've already done approvals though!)
    before = ajna.balanceOf(ajna_whale)
    ajna.approve(yvdai_pool, 2**256 - 1, {"from": ajna_whale})
    yvdai_pool.notifyRewardAmount(ajna, ajna_amount, {"from": ajna_whale})
    assert before == ajna.balanceOf(ajna_whale) + ajna_amount

    # do prisma too
    before = prisma.balanceOf(prisma_whale)
    prisma.approve(yvdai_pool, 2**256 - 1, {"from": prisma_whale})
    yvdai_pool.notifyRewardAmount(prisma, prisma_amount, {"from": prisma_whale})
    assert before == prisma.balanceOf(prisma_whale) + prisma_amount

    # sleep to gain some earnings
    chain.sleep(86400)
    chain.mine(1)

    # check claimable earnings, get reward
    assert yvdai_pool.getRewardForDuration(ajna) > 0
    assert yvdai_pool.getRewardForDuration(prisma) > 0
    ajna_earned = yvdai_pool.earned(yvdai_whale, ajna)
    prisma_earned = yvdai_pool.earned(yvdai_whale, prisma)
    assert ajna_earned > 0
    assert prisma_earned > 0
    yvdai_pool.getReward({"from": yvdai_whale})
    assert ajna.balanceOf(yvdai_whale) >= ajna_earned
    assert prisma.balanceOf(yvdai_whale) >= prisma_earned

    # sleep to gain some earnings
    chain.sleep(86400)
    chain.mine(1)

    # claim ajna and prisma individually
    assert yvdai_pool.getRewardForDuration(ajna) > 0
    assert yvdai_pool.getRewardForDuration(prisma) > 0
    ajna_earned = yvdai_pool.earned(yvdai_whale, ajna)
    prisma_earned = yvdai_pool.earned(yvdai_whale, prisma)
    ajna_before = ajna.balanceOf(yvdai_whale)
    prisma_before = prisma.balanceOf(yvdai_whale)
    assert ajna_earned > 0
    assert prisma_earned > 0

    yvdai_pool.getOneReward(ajna, {"from": yvdai_whale})
    ajna_middle = ajna.balanceOf(yvdai_whale)
    prisma_middle = prisma.balanceOf(yvdai_whale)
    assert ajna_middle >= ajna_before + ajna_earned
    assert prisma_middle == prisma_before

    yvdai_pool.getOneReward(prisma, {"from": yvdai_whale})
    prisma_final = prisma.balanceOf(yvdai_whale)
    ajna_final = ajna.balanceOf(yvdai_whale)
    assert prisma_final >= prisma_middle + prisma_earned
    assert ajna_final == ajna_middle

    # sleep to gain some earnings
    chain.sleep(86400)
    chain.mine(1)

    # can't withdraw zero
    with brownie.reverts("Must be >0"):
        yvdai_pool.withdraw(0, {"from": yvdai_whale})

    # exit, check that we have the same principal and earned more rewards
    yvdai_pool.exit({"from": yvdai_whale})
    assert yvdai_starting == yvdai.balanceOf(yvdai_whale)
    assert ajna.balanceOf(yvdai_whale) > ajna_final
    assert prisma.balanceOf(yvdai_whale) > prisma_final

    # check our setters
    with brownie.reverts("Rewards active"):
        yvdai_pool.setRewardsDuration(ajna, 100e18, {"from": ajna_whale})
    with brownie.reverts("No zero address"):
        yvdai_pool.setZapContract(ZERO_ADDRESS, {"from": gov})
    yvdai_pool.setZapContract(zap, {"from": gov})

    # sleep to get past our rewards window
    chain.sleep(86400 * 6)
    with brownie.reverts("Must be >0"):
        yvdai_pool.setRewardsDuration(ajna, 0, {"from": ajna_whale})
    with brownie.reverts("!authorized"):
        yvdai_pool.setRewardsDuration(ajna, 100e18, {"from": gov})
    yvdai_pool.setRewardsDuration(ajna, 86400 * 14, {"from": ajna_whale})
    assert dai.balanceOf(zap) == 0


def test_insanity(
    gov,
    yvdai,
    yvdai_amount,
    yvdai_whale,
    yvmkusd,
    yvmkusd_amount,
    yvmkusd_whale,
    ajna,
    ajna_amount,
    ajna_whale,
    registry,
    zap,
    yvdai_pool,
    yvmkusd_pool,
    dai,
    dai_whale,
    dai_amount,
):
    # Approve and deposit to the staking contract
    yvdai_starting = yvdai.balanceOf(yvdai_whale)
    yvdai.approve(yvdai_pool, 2**256 - 1, {"from": yvdai_whale})
    yvdai_pool.stake(yvdai_amount, {"from": yvdai_whale})
    assert yvdai_pool.balanceOf(yvdai_whale) == yvdai_amount

    # add ajna and grant role to whale
    week = 7 * 86400
    yvdai_pool.addReward(ajna, ajna_whale, week, {"from": gov})

    # now we should be able to notify (make sure we've already done approvals though!)
    before = ajna.balanceOf(ajna_whale)
    ajna.approve(yvdai_pool, 2**256 - 1, {"from": ajna_whale})
    yvdai_pool.notifyRewardAmount(ajna, ajna_amount, {"from": ajna_whale})
    assert before == ajna.balanceOf(ajna_whale) + ajna_amount

    # make sure we start with nothing
    assert ajna.balanceOf(yvdai_whale) == 0

    # sleep to gain some earnings
    chain.sleep(86400)
    chain.mine(1)

    # check claimable earnings, get reward
    earned = yvdai_pool.earned(yvdai_whale, ajna)
    assert earned > 0
    assert yvdai_pool.userRewardPerTokenPaid(yvdai_whale, ajna) == 0

    # rewardPerToken() was last calculated here
    print("\nReward per token before getReward call:", yvdai_pool.rewardPerToken(ajna))
    print("rewardPerTokenStored:", yvdai_pool.rewardData(ajna)["rewardPerTokenStored"])
    print(
        "userRewardPerTokenPaid:", yvdai_pool.userRewardPerTokenPaid(yvdai_whale, ajna)
    )
    print("lastTimeRewardApplicable:", yvdai_pool.lastTimeRewardApplicable(ajna))
    print("lastUpdateTime:", yvdai_pool.rewardData(ajna)["lastUpdateTime"])
    print("rewardRate:", yvdai_pool.rewardData(ajna)["rewardRate"])
    print("_totalSupply:", yvdai_pool.totalSupply())
    print("Earned:", yvdai_pool.earned(yvdai_whale, ajna))
    print("rewards:", yvdai_pool.rewards(yvdai_whale, ajna))

    yvdai_pool.getReward({"from": yvdai_whale})

    print("\nReward per token after getReward:", yvdai_pool.rewardPerToken(ajna))
    print("rewardPerTokenStored:", yvdai_pool.rewardData(ajna)["rewardPerTokenStored"])
    print(
        "userRewardPerTokenPaid:", yvdai_pool.userRewardPerTokenPaid(yvdai_whale, ajna)
    )
    print("lastTimeRewardApplicable:", yvdai_pool.lastTimeRewardApplicable(ajna))
    print("lastUpdateTime:", yvdai_pool.rewardData(ajna)["lastUpdateTime"])
    print("rewardRate:", yvdai_pool.rewardData(ajna)["rewardRate"])
    print("_totalSupply:", yvdai_pool.totalSupply())
    print("Earned:", yvdai_pool.earned(yvdai_whale, ajna))
    print("rewards:", yvdai_pool.rewards(yvdai_whale, ajna))

    claimed = ajna.balanceOf(yvdai_whale)
    print("Claimed:", claimed)
    staking_token = interface.IERC20(yvdai_pool.stakingToken())
    reward_per_token = yvdai_pool.userRewardPerTokenPaid(yvdai_whale, ajna)
    tokens = int(yvdai_pool.balanceOf(yvdai_whale) / (10 ** staking_token.decimals()))
    answer = reward_per_token * tokens
    assert answer == claimed

    # sleep to gain some earnings
    chain.sleep(86400)
    chain.mine(1)

    print(
        "\nReward per token after sleeping for a day:", yvdai_pool.rewardPerToken(ajna)
    )
    print("rewardPerTokenStored:", yvdai_pool.rewardData(ajna)["rewardPerTokenStored"])
    print(
        "userRewardPerTokenPaid:", yvdai_pool.userRewardPerTokenPaid(yvdai_whale, ajna)
    )
    print("lastTimeRewardApplicable:", yvdai_pool.lastTimeRewardApplicable(ajna))
    print("lastUpdateTime:", yvdai_pool.rewardData(ajna)["lastUpdateTime"])
    print("rewardRate:", yvdai_pool.rewardData(ajna)["rewardRate"])
    print("_totalSupply:", yvdai_pool.totalSupply())
    print("Earned:", yvdai_pool.earned(yvdai_whale, ajna))
    print("rewards:", yvdai_pool.rewards(yvdai_whale, ajna))

    yvdai_pool.getReward({"from": yvdai_whale})

    print("\nReward per token after getReward:", yvdai_pool.rewardPerToken(ajna))
    print("rewardPerTokenStored:", yvdai_pool.rewardData(ajna)["rewardPerTokenStored"])
    print(
        "userRewardPerTokenPaid:", yvdai_pool.userRewardPerTokenPaid(yvdai_whale, ajna)
    )
    print("lastTimeRewardApplicable:", yvdai_pool.lastTimeRewardApplicable(ajna))
    print("lastUpdateTime:", yvdai_pool.rewardData(ajna)["lastUpdateTime"])
    print("rewardRate:", yvdai_pool.rewardData(ajna)["rewardRate"])
    print("_totalSupply:", yvdai_pool.totalSupply())
    print("Earned:", yvdai_pool.earned(yvdai_whale, ajna))
    print("rewards:", yvdai_pool.rewards(yvdai_whale, ajna))

    # this hasn't been reset to zero yet
    claimed = ajna.balanceOf(yvdai_whale)
    print("Claimed:", claimed)
    staking_token = interface.IERC20(yvdai_pool.stakingToken())
    reward_per_token = yvdai_pool.userRewardPerTokenPaid(yvdai_whale, ajna)
    tokens = int(yvdai_pool.balanceOf(yvdai_whale) / (10 ** staking_token.decimals()))
    answer = reward_per_token * tokens
    assert answer == claimed


def test_sweep_rewards(
    gov,
    yvdai,
    yvdai_amount,
    yvdai_whale,
    yvmkusd,
    yvmkusd_amount,
    yvmkusd_whale,
    ajna,
    ajna_amount,
    ajna_whale,
    registry,
    zap,
    yvdai_pool,
    yvmkusd_pool,
    dai,
    dai_whale,
    dai_amount,
):
    # Approve and deposit to the staking contract
    yvdai_starting = yvdai.balanceOf(yvdai_whale)
    yvdai.approve(yvdai_pool, 2**256 - 1, {"from": yvdai_whale})
    yvdai_pool.stake(yvdai_amount, {"from": yvdai_whale})
    assert yvdai_pool.balanceOf(yvdai_whale) == yvdai_amount

    # add ajna and grant role to whale
    week = 7 * 86400
    yvdai_pool.addReward(ajna, ajna_whale, week, {"from": gov})

    # now we should be able to notify (make sure we've already done approvals though!)
    before = ajna.balanceOf(ajna_whale)
    ajna.approve(yvdai_pool, 2**256 - 1, {"from": ajna_whale})
    yvdai_pool.notifyRewardAmount(ajna, ajna_amount, {"from": ajna_whale})
    assert before == ajna.balanceOf(ajna_whale) + ajna_amount

    # sleep to gain some earnings
    chain.sleep(86400)
    chain.mine(1)

    # check claimable earnings, get reward
    earned = yvdai_pool.earned(yvdai_whale, ajna)
    assert earned > 0
    yvdai_pool.getReward({"from": yvdai_whale})
    claimed = ajna.balanceOf(yvdai_whale)

    # do >= since we (sometimes?) get extra in the block it takes to harvest
    assert claimed >= earned
    print("Earned:", earned / 1e18, "Claimed:", claimed / 1e18)

    # check that we can't sweep out yvOP or the staking token
    with brownie.reverts():
        yvdai_pool.recoverERC20(yvdai_pool.rewardTokens(0), 10e18, {"from": gov})
    with brownie.reverts():
        yvdai_pool.recoverERC20(yvdai_pool.stakingToken(), 10e18, {"from": gov})

    # we can sweep out DAI tho
    dai.transfer(yvdai_pool, 100e18, {"from": dai_whale})
    assert dai.balanceOf(yvdai_pool) > 0
    yvdai_pool.recoverERC20(dai, 100e18, {"from": gov})
    assert dai.balanceOf(yvdai_pool) == 0

    # sleep 91 days so we can sweep out rewards
    chain.sleep(86400 * 100)
    chain.mine(1)
    earned = yvdai_pool.earned(yvdai_whale, ajna)
    assert earned > 0
    assert ajna.balanceOf(yvdai_pool) > 0

    # amount doesn't matter since we auto-sweep all rewards token
    yvdai_pool.recoverERC20(yvdai_pool.rewardTokens(0), 10e18, {"from": gov})
    assert ajna.balanceOf(yvdai_pool) == 0

    # this hasn't been reset to zero yet. multiply by amount of whole tokens we have
    staking_token = interface.IERC20(yvdai_pool.stakingToken())
    reward_per_token = yvdai_pool.userRewardPerTokenPaid(yvdai_whale, ajna)
    tokens = int(yvdai_pool.balanceOf(yvdai_whale) / (10 ** staking_token.decimals()))
    answer = reward_per_token * tokens
    assert answer == claimed

    # check our earned, should be zeroed
    earned = yvdai_pool.earned(yvdai_whale, ajna)
    assert earned == 0
    assert yvdai_pool.rewardPerToken(ajna) == 0
    assert yvdai_pool.rewards(yvdai_whale, ajna) == 0

    # make sure we can get rewards and nothing happens
    before = ajna.balanceOf(yvdai_whale)
    yvdai_pool.getReward({"from": yvdai_whale})
    after = ajna.balanceOf(yvdai_whale)
    assert before == after

    # now this should be zero since we called updateReward when calling getReward
    assert yvdai_pool.userRewardPerTokenPaid(yvdai_whale, ajna) == 0

    # make sure our whale can still withdraw
    yvdai_pool.exit({"from": yvdai_whale})
    assert yvdai_starting == yvdai.balanceOf(yvdai_whale)
    assert ajna.balanceOf(yvdai_whale) > 0
    assert yvdai_pool.userRewardPerTokenPaid(yvdai_whale, ajna) == 0

    # check that we can't stake or zap in
    with brownie.reverts("Pool retired"):
        yvdai_pool.stake(yvdai_amount, {"from": yvdai_whale})
    registry.addStakingPool(yvdai_pool, yvdai, False, {"from": gov})
    dai.approve(zap, 2**256 - 1, {"from": dai_whale})
    with brownie.reverts("Pool retired"):
        zap.zapInLegacy(yvdai, dai_amount, {"from": dai_whale})


def test_extend_rewards(
    gov,
    yvdai,
    yvdai_amount,
    yvdai_whale,
    yvmkusd,
    yvmkusd_amount,
    yvmkusd_whale,
    ajna,
    ajna_amount,
    ajna_whale,
    registry,
    zap,
    yvdai_pool,
    yvmkusd_pool,
):
    # Approve and deposit to the staking contract
    yvdai_starting = yvdai.balanceOf(yvdai_whale)
    yvdai.approve(yvdai_pool, 2**256 - 1, {"from": yvdai_whale})
    yvdai_pool.stake(yvdai_amount, {"from": yvdai_whale})
    assert yvdai_pool.balanceOf(yvdai_whale) == yvdai_amount

    # add ajna and grant role to whale
    week = 7 * 86400
    yvdai_pool.addReward(ajna, ajna_whale, week, {"from": gov})

    # now we should be able to notify (make sure we've already done approvals though!)
    before = ajna.balanceOf(ajna_whale)
    ajna.approve(yvdai_pool, 2**256 - 1, {"from": ajna_whale})
    yvdai_pool.notifyRewardAmount(ajna, ajna_amount, {"from": ajna_whale})
    assert before == ajna.balanceOf(ajna_whale) + ajna_amount

    # sleep to gain some earnings
    chain.sleep(86400)
    chain.mine(1)

    # check claimable earnings, get reward
    earned = yvdai_pool.earned(yvdai_whale, ajna)
    assert earned > 0
    yvdai_pool.getReward({"from": yvdai_whale})
    claimed = ajna.balanceOf(yvdai_whale)
    assert ajna.balanceOf(yvdai_whale) >= earned
    assert yvdai_pool.earned(yvdai_whale, ajna) == 0

    # do >= since we (sometimes?) get extra in the block it takes to harvest
    assert claimed >= earned
    print("Earned:", earned / 1e18, "Claimed:", claimed / 1e18)

    # sleep to gain some earnings
    chain.sleep(86400)
    chain.mine(1)

    # check claimable earnings again
    earned = yvdai_pool.earned(yvdai_whale, ajna)
    assert earned > 0
    print("Earned:", earned / 1e18)

    # add more rewards
    yvdai_pool.notifyRewardAmount(ajna, ajna_amount, {"from": ajna_whale})

    # can't add too much (but tbh hard to make it overflow with a week as rewardsDuration)
    time_remaining = yvdai_pool.rewardData(ajna)["periodFinish"] - chain.time()
    leftover = time_remaining * yvdai_pool.rewardData(ajna)["rewardRate"]
    overflow_amount = 240_000_000e18
    to_check = (leftover + overflow_amount) / yvdai_pool.rewardData(ajna)[
        "rewardsDuration"
    ]
    # if this check passes, we wouldn't overflow even with a huge amount of AJNA (yay)
    assert (
        to_check
        < (ajna.balanceOf(yvdai_pool) + overflow_amount)
        / yvdai_pool.rewardData(ajna)["rewardsDuration"]
    )

    # check claimable earnings, make sure we have at least as much as before
    new_earned = yvdai_pool.earned(yvdai_whale, ajna)
    assert new_earned >= earned
    print("New Earned after notify:", new_earned / 1e18)

    # sleep to gain some earnings
    chain.sleep(86400)
    chain.mine(1)

    # check claimable earnings, make sure we have more than before
    new_earned = yvdai_pool.earned(yvdai_whale, ajna)
    before_balance = ajna.balanceOf(yvdai_whale)
    yvdai_pool.getReward({"from": yvdai_whale})
    assert ajna.balanceOf(yvdai_whale) - before_balance >= earned
    print("New Earned after sleep:", new_earned / 1e18)

    # exit, check that we have the same principal and earned more rewards
    yvdai_pool.exit({"from": yvdai_whale})
    assert yvdai_starting == yvdai.balanceOf(yvdai_whale)
    assert ajna.balanceOf(yvdai_whale) > earned


def test_zap_in(
    gov,
    yvdai,
    yvdai_amount,
    yvdai_whale,
    dai,
    dai_amount,
    dai_whale,
    yvmkusd,
    yvmkusd_amount,
    yvmkusd_whale,
    ajna,
    ajna_amount,
    ajna_whale,
    registry,
    zap,
    yvdai_pool,
    yvmkusd_pool,
    RELATIVE_APPROX,
):
    # Approve and zap into to the staking contract
    dai_starting = dai.balanceOf(dai_whale)
    dai.approve(zap, 2**256 - 1, {"from": dai_whale})

    # can't deposit into a contract that isn't in our registry
    with brownie.reverts("staking pool doesn't exist"):
        zap.zapInLegacy(yvdai, dai_amount, {"from": dai_whale})

    # can't zap into zero address (vault deposit() step will fail)
    with brownie.reverts():
        zap.zapInLegacy(ZERO_ADDRESS, dai_amount, {"from": dai_whale})

    # Add our staking contract to our registry
    registry.addStakingPool(yvdai_pool, yvdai, False, {"from": gov})

    # need to pretend to stakeFor directly from zap contract to hit the require
    with brownie.reverts("Must be >0"):
        yvdai_pool.stakeFor(dai_whale, 0, {"from": zap})

    # zap in, but can't zap zero
    with brownie.reverts():
        zap.zapInLegacy(yvdai, 0, {"from": dai_whale})
    zap.zapInLegacy(yvdai, dai_amount, {"from": dai_whale})
    balance = yvdai_pool.balanceOf(dai_whale)
    assert balance > 0
    print("Staked balance of yvDAI, should be ~1000:", balance / 1e18)

    # check that our zap has zero balance
    zap_balance = yvdai_pool.balanceOf(zap)
    assert zap_balance == 0
    with brownie.reverts():
        yvdai_pool.withdraw(100e18, {"from": zap})

    # add ajna and grant role to whale
    week = 7 * 86400
    yvdai_pool.addReward(ajna, ajna_whale, week, {"from": gov})

    # now we should be able to notify (make sure we've already done approvals though!)
    before = ajna.balanceOf(ajna_whale)
    ajna.approve(yvdai_pool, 2**256 - 1, {"from": ajna_whale})
    yvdai_pool.notifyRewardAmount(ajna, ajna_amount, {"from": ajna_whale})
    assert before == ajna.balanceOf(ajna_whale) + ajna_amount

    # no problem to zap in a bit more
    chain.sleep(1)
    chain.mine(1)
    zap.zapInLegacy(yvdai, dai_amount, {"from": dai_whale})

    # sleep to gain some earnings
    chain.sleep(86400)
    chain.mine(1)

    # check claimable earnings, get reward
    earned = yvdai_pool.earned(dai_whale, ajna)
    assert earned > 0
    yvdai_pool.getReward({"from": dai_whale})
    assert pytest.approx(ajna.balanceOf(dai_whale), rel=RELATIVE_APPROX) == earned

    # sleep to gain some earnings
    chain.sleep(86400)
    chain.mine(1)

    # exit, check that we have the same principal and earned more rewards
    yvdai_pool.exit({"from": dai_whale})
    yvdai.withdraw({"from": dai_whale})
    assert pytest.approx(dai_starting, rel=RELATIVE_APPROX) == dai.balanceOf(dai_whale)
    assert ajna.balanceOf(dai_whale) > earned

    # check that no one else can use stakeFor (even gov!)
    yvdai.approve(yvdai_pool, 2**256 - 1, {"from": gov})
    yvdai.transfer(gov, 100e18, {"from": yvdai_whale})
    with brownie.reverts("!authorized"):
        yvdai_pool.stakeFor(gov, 100e18, {"from": gov})

    # zero address for registry will revert on zap in
    zap.setPoolRegistry(ZERO_ADDRESS, {"from": gov})
    with brownie.reverts():
        zap.zapInLegacy(yvdai, dai_amount, {"from": dai_whale})


def test_zap_out(
    gov,
    yvdai,
    yvdai_amount,
    yvdai_whale,
    dai,
    dai_amount,
    dai_whale,
    yvmkusd,
    yvmkusd_amount,
    yvmkusd_whale,
    ajna,
    ajna_amount,
    ajna_whale,
    registry,
    zap,
    yvdai_pool,
    yvmkusd_pool,
    RELATIVE_APPROX,
):
    # Approve and deposit to the staking contract
    yvdai_starting = yvdai.balanceOf(yvdai_whale)
    yvdai.approve(yvdai_pool, 2**256 - 1, {"from": yvdai_whale})
    yvdai_pool.stake(yvdai_amount, {"from": yvdai_whale})
    assert yvdai_pool.balanceOf(yvdai_whale) == yvdai_amount

    # Add our staking contract to our registry
    registry.addStakingPool(yvdai_pool, yvdai, False, {"from": gov})

    # add ajna and grant role to whale
    week = 7 * 86400
    yvdai_pool.addReward(ajna, ajna_whale, week, {"from": gov})

    # now we should be able to notify (make sure we've already done approvals though!)
    before = ajna.balanceOf(ajna_whale)
    ajna.approve(yvdai_pool, 2**256 - 1, {"from": ajna_whale})
    yvdai_pool.notifyRewardAmount(ajna, ajna_amount, {"from": ajna_whale})
    assert before == ajna.balanceOf(ajna_whale) + ajna_amount

    # sleep to gain some earnings
    chain.sleep(86400)
    chain.mine(1)

    # check claimable earnings, get reward
    earned = yvdai_pool.earned(yvdai_whale, ajna)
    assert earned > 0
    yvdai_pool.getReward({"from": yvdai_whale})
    assert pytest.approx(ajna.balanceOf(yvdai_whale), rel=RELATIVE_APPROX) == earned

    # sleep to gain some earnings
    chain.sleep(86400)
    chain.mine(1)

    # zap out (exit) check that we have the same principal and earned more rewards
    dai_balance = dai.balanceOf(yvdai_whale)
    zap.zapOutLegacy(yvdai, yvdai_amount, True, {"from": yvdai_whale})
    dai_out = dai.balanceOf(yvdai_whale) - dai_balance
    print(
        "yvDAI In * PPS:",
        yvdai_amount * yvdai.pricePerShare() / 1e36,
        "DAI Out:",
        dai_out / 1e18,
    )
    assert ajna.balanceOf(yvdai_whale) > earned


def test_registry(
    gov,
    yvdai,
    yvdai_amount,
    yvdai_whale,
    dai,
    dai_amount,
    dai_whale,
    yvmkusd,
    yvmkusd_amount,
    yvmkusd_whale,
    ajna,
    ajna_whale,
    registry,
    zap,
    yvdai_pool,
    yvmkusd_pool,
    RELATIVE_APPROX,
    StakingRewardsMulti,
    strategist,
):
    # check that dai isn't registered yet
    assert registry.isRegistered(dai.address) == False

    # not just anyone can add a pool
    with brownie.reverts():
        registry.addStakingPool(yvdai_pool, yvdai, False, {"from": strategist})

    # Add our staking contract to our registry
    registry.addStakingPool(yvdai_pool, yvdai, False, {"from": gov})
    assert registry.isRegistered(yvdai.address) == True

    # can't have a mismatch in tokens
    with brownie.reverts():
        registry.addStakingPool(yvmkusd_pool, yvdai, False, {"from": gov})

    # can't replace a pool that hasn't been added yet
    with brownie.reverts("token isn't registered, can't replace"):
        registry.addStakingPool(yvmkusd_pool, yvmkusd, True, {"from": gov})

    # can't add another pool for the same underlying without replacing
    yvdai_pool_too = gov.deploy(
        StakingRewardsMulti,
        gov.address,
        yvdai.address,
        zap.address,
    )
    with brownie.reverts():
        registry.addStakingPool(yvdai_pool_too, yvdai, False, {"from": gov})

    # check that the correct pools are showing up
    assert registry.stakingPool(yvdai.address) == yvdai_pool.address
    assert registry.isStakingPoolEndorsed(yvdai_pool) == True
    assert registry.isStakingPoolEndorsed(yvdai_pool_too) == False

    # replace instead of adding
    registry.addStakingPool(yvdai_pool_too, yvdai, True, {"from": gov})
    assert registry.stakingPool(yvdai.address) == yvdai_pool_too.address

    # make sure we can't add one with incorrect gov
    yvdai_pool_three = strategist.deploy(
        StakingRewardsMulti,
        strategist.address,
        yvdai.address,
        zap.address,
    )

    with brownie.reverts():
        registry.addStakingPool(yvdai_pool_three, yvdai, True, {"from": gov})

    # zero address reverts
    with brownie.reverts():
        registry.addStakingPool(ZERO_ADDRESS, yvdai, True, {"from": gov})

    with brownie.reverts():
        registry.addStakingPool(yvdai_pool_three, ZERO_ADDRESS, True, {"from": gov})

    # check our endorsing is working properly
    assert registry.isStakingPoolEndorsed(yvdai_pool_three) == False
    assert registry.isStakingPoolEndorsed(yvdai_pool_too) == True
    assert registry.isStakingPoolEndorsed(yvdai_pool) == False

    # make sure our length is what we expect for tokens
    assert registry.numTokens() == 1
    assert registry.isRegistered(yvmkusd.address) == False
    assert registry.isStakingPoolEndorsed(yvmkusd_pool) == False

    # deploy yvmkusd via registry cloning
    # will revert without stakingContract set
    with brownie.reverts():
        registry.cloneAndAddStakingPool(yvmkusd, {"from": gov})

    # only owner can set default contracts
    with brownie.reverts():
        registry.setDefaultContracts(yvdai_pool, zap, {"from": yvdai_whale})

    registry.setDefaultContracts(yvdai_pool, zap, {"from": gov})

    # only pool endorsers can set
    with brownie.reverts("!authorized"):
        registry.cloneAndAddStakingPool(yvmkusd, {"from": yvdai_whale})

    # clone and add
    registry.cloneAndAddStakingPool(yvmkusd, {"from": gov})

    # add first yvmkusd staking as replacement
    registry.addStakingPool(yvmkusd_pool, yvmkusd, True, {"from": gov})
    assert registry.numTokens() == 2
    assert registry.isStakingPoolEndorsed(yvmkusd_pool) == True
    assert registry.isRegistered(yvmkusd.address) == True

    # check our tokens view
    assert registry.tokens(0) == yvdai.address
    assert registry.tokens(1) == yvmkusd.address
