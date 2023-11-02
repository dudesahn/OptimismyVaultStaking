import pytest
from brownie import config, project
from brownie import Contract, interface


# Function scoped isolation fixture to enable xdist.
# Snapshots the chain before each test and reverts after test completion.
@pytest.fixture(scope="function", autouse=True)
def shared_setup(fn_isolation):
    pass


@pytest.fixture
def gov(accounts):
    yield accounts.at("0xF5d9D6133b698cE29567a90Ab35CfB874204B3A7", force=True)


@pytest.fixture
def user(accounts):
    yield accounts[0]


@pytest.fixture
def rewards(accounts):
    yield accounts[1]


@pytest.fixture
def guardian(accounts):
    yield accounts[2]


@pytest.fixture
def management(accounts):
    yield accounts[3]


@pytest.fixture
def strategist(accounts):
    yield accounts.at("0xC6387E937Bcef8De3334f80EDC623275d42457ff", force=True)


@pytest.fixture
def keeper(accounts):
    yield accounts[5]


@pytest.fixture
def whale(accounts):
    yield accounts.at("0xBA12222222228d8Ba445958a75a0704d566BF2C8", force=True)


@pytest.fixture
def yvdai(deploy_vault):
    token_address = "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1"  # DAI
    yield deploy_vault(token_address)


@pytest.fixture
def yvdai_amount(yvdai):
    yvdai_amount = 100 * 10 ** yvdai.decimals()
    yield yvdai_amount


@pytest.fixture
def yvdai_whale(whale, yvdai, yvdai_amount, user):
    dai = interface.IERC20(yvdai.asset())
    dai.approve(yvdai, yvdai_amount, {"from": whale})
    yvdai.deposit(yvdai_amount, user, {"from": whale})
    yield user


@pytest.fixture
def yvusdc(deploy_vault):
    token_address = "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85"  # tusdc
    yield deploy_vault(token_address)


@pytest.fixture
def yvusdc_amount():
    yvusdc_amount = 600e6
    yield yvusdc_amount


@pytest.fixture
def yvusdc_whale(whale, yvusdc, yvusdc_amount, user):
    usdc = interface.IERC20(yvusdc.asset())
    usdc.approve(yvusdc, yvusdc_amount, {"from": whale})
    yvusdc.deposit(yvusdc_amount, user, {"from": whale})
    yield user


@pytest.fixture
def yvop(deploy_vault):
    token_address = "0x4200000000000000000000000000000000000042"  # $OP
    yield deploy_vault(token_address)


@pytest.fixture
def yvop_amount(yvop):
    yvop_amount = 500 * 10 ** yvop.decimals()
    yield yvop_amount


@pytest.fixture
def yvop_whale(whale, yvop, yvop_amount, user):
    op = interface.IERC20(yvop.asset())
    op.approve(yvop, yvop_amount, {"from": whale})
    yvop.deposit(yvop_amount, user, {"from": whale})
    yield user


@pytest.fixture
def dai():
    token_address = "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1"  # DAI
    yield interface.IERC20(token_address)


@pytest.fixture
def dai_amount(yvdai):
    dai_amount = 1_000 * 10 ** yvdai.decimals()
    yield dai_amount


@pytest.fixture
def dai_whale(accounts):
    dai_whale = accounts.at(
        "0x7B7B957c284C2C227C980d6E2F804311947b84d0", force=True
    )  # ~3m DAI
    yield dai_whale


@pytest.fixture
def deploy_vault(MockVault, gov):
    def deploy_vault(asset, management=gov):
        vault = management.deploy(MockVault, asset)
        return vault

    yield deploy_vault


@pytest.fixture
def registry(StakingRewardsRegistry, gov):
    registry = gov.deploy(StakingRewardsRegistry)
    registry.setPoolEndorsers(gov, True, {"from": gov})
    registry.setApprovedPoolOwner(gov, True, {"from": gov})
    yield registry


@pytest.fixture
def live_registry(StakingRewardsRegistry):
    live_registry = StakingRewardsRegistry.at(
        "0x8ED9F6343f057870F1DeF47AaE7CD88dfAA049A8"
    )
    yield live_registry


@pytest.fixture
def zap(StakingRewardsZap, gov, registry):
    zap = gov.deploy(StakingRewardsZap, registry.address)
    yield zap


@pytest.fixture
def new_zap(StakingRewardsZap, gov, live_registry):
    new_zap = gov.deploy(StakingRewardsZap, live_registry)
    yield new_zap


@pytest.fixture
def old_live_zap(StakingRewardsZapOld):
    old_live_zap = StakingRewardsZapOld.at("0xd155F5bF8a475007Fa369e6314C3673e4Bb1e292")
    yield old_live_zap


@pytest.fixture
def yvdai_pool(StakingRewards, gov, registry, yvdai, yvop, zap):
    yvdai_pool = gov.deploy(
        StakingRewards,
        gov.address,
        gov.address,
        yvop.address,
        yvdai.address,
        zap.address,
    )
    yield yvdai_pool


@pytest.fixture
def yvdai_pool_live(StakingRewards):
    yvdai_pool_live = StakingRewards.at("0xf8126EF025651E1B313a6893Fcf4034F4F4bD2aA")
    yield yvdai_pool_live


# @pytest.fixture
# def yvdai_pool_clonable(StakingRewardsClonable, gov, registry, yvdai, yvop, zap):
#     yvdai_pool_clonable = gov.deploy(
#         StakingRewardsClonable,
#         gov.address,
#         gov.address,
#         yvop.address,
#         yvdai.address,
#         zap.address,
#     )
#     yield yvdai_pool_clonable


@pytest.fixture
def yvusdc_pool(StakingRewards, gov, registry, yvusdc, yvop, zap):
    yvusdc_pool = gov.deploy(
        StakingRewards,
        gov.address,
        gov.address,
        yvop.address,
        yvusdc.address,
        zap.address,
    )
    yield yvusdc_pool


@pytest.fixture(scope="session")
def RELATIVE_APPROX():
    yield 1e-2
