import pytest
from brownie import config
from brownie import Contract, interface


# Function scoped isolation fixture to enable xdist.
# Snapshots the chain before each test and reverts after test completion.
@pytest.fixture(scope="function", autouse=True)
def shared_setup(fn_isolation):
    pass


@pytest.fixture(scope="session")
def gov(accounts):  # ychad on mainnet
    yield accounts.at("0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52", force=True)


@pytest.fixture(scope="session")
def rando(accounts):
    yield accounts[0]


@pytest.fixture(scope="session")
def strategist(accounts):
    yield accounts.at("0xC6387E937Bcef8De3334f80EDC623275d42457ff", force=True)


############# STAKING TOKENS #############


@pytest.fixture(scope="session")
def yvdai():
    token_address = "0xdA816459F1AB5631232FE5e97a05BBBb94970c95"  # this is our V2 vault (yvDAI 0.4.3)
    yield interface.IVaultFactory045(token_address)


@pytest.fixture(scope="session")
def yvdai_amount(yvdai):
    yvdai_amount = 100 * 10 ** yvdai.decimals()
    yield yvdai_amount


@pytest.fixture(scope="session")
def yvdai_whale(accounts):
    yvdai_whale = accounts.at(
        "0xb619C9F4D833B7aBa7b49735524B3671C8281f73", force=True
    )  # ~1M yvDAI
    yield yvdai_whale


@pytest.fixture(scope="session")
def yvmkusd():
    token_address = "0x04AeBe2e4301CdF5E9c57B01eBdfe4Ac4B48DD13"  # this is our V3 vault (yvmkUSD-A V3)
    yield Contract(token_address)


@pytest.fixture(scope="session")
def yvmkusd_amount(yvmkusd):
    yvmkusd_amount = 100 * 10 ** yvmkusd.decimals()
    yield yvmkusd_amount


@pytest.fixture(scope="session")
def yvmkusd_whale(accounts):
    yvmkusd_whale = accounts.at(
        "0x93A62dA5a14C80f265DAbC077fCEE437B1a0Efde", force=True
    )  # ~26k yvmkusd
    yield yvmkusd_whale


############# REWARD TOKENS #############


@pytest.fixture(scope="session")
def ajna():
    token_address = "0x9a96ec9B57Fb64FbC60B423d1f4da7691Bd35079"  # AJNA token
    yield interface.IERC20(token_address)


@pytest.fixture(scope="session")
def ajna_amount(ajna):
    ajna_amount = 5_000 * 10 ** ajna.decimals()
    yield ajna_amount


@pytest.fixture(scope="session")
def ajna_whale(accounts):
    ajna_whale = accounts.at(
        "0x74d5b005ca64a5C9EE3611Bdc6F6C02D93C84b2f", force=True
    )  # ~>200M ajna, grants contract
    yield ajna_whale


@pytest.fixture(scope="session")
def prisma():
    token_address = "0xdA47862a83dac0c112BA89c6abC2159b95afd71C"  # PRISMA token
    yield interface.IERC20(token_address)


@pytest.fixture(scope="session")
def prisma_amount(prisma):
    prisma_amount = 5_000 * 10 ** prisma.decimals()
    yield prisma_amount


@pytest.fixture(scope="session")
def prisma_whale(accounts):
    prisma_whale = accounts.at(
        "0x06bDF212C290473dCACea9793890C5024c7Eb02c", force=True
    )  # ~>200M prisma, vault contract
    yield prisma_whale


############# UNDERLYING TOKENS #############


@pytest.fixture(scope="session")
def dai():
    token_address = "0x6B175474E89094C44Da98b954EedeAC495271d0F"  # DAI
    yield interface.IERC20(token_address)


@pytest.fixture(scope="session")
def dai_amount(yvdai):
    dai_amount = 1_000 * 10 ** yvdai.decimals()
    yield dai_amount


@pytest.fixture(scope="session")
def dai_whale(accounts):
    dai_whale = accounts.at(
        "0x075e72a5eDf65F0A5f44699c7654C1a76941Ddc8", force=True
    )  # ~278M DAI, pulse sacrifice lol
    yield dai_whale


@pytest.fixture(scope="session")
def mkusd():
    token_address = "0x4591DBfF62656E7859Afe5e45f6f47D3669fBB28"  # mkUSD
    yield interface.IERC20(token_address)


@pytest.fixture(scope="session")
def mkusd_amount(yvmkusd):
    mkusd_amount = 1_000 * 10 ** yvmkusd.decimals()
    yield mkusd_amount


@pytest.fixture(scope="session")
def mkusd_whale(accounts):
    mkusd_whale = accounts.at(
        "0xfdCE0267803C6a0D209D3721d2f01Fd618e9CBF8", force=True
    )  # ~2.5M mkUSD, prisma fee receiver
    yield mkusd_whale


@pytest.fixture
def registry(StakingRewardsRegistry, gov):
    registry = gov.deploy(StakingRewardsRegistry)
    registry.setPoolEndorsers(gov, True, {"from": gov})
    registry.setApprovedPoolOwner(gov, True, {"from": gov})
    yield registry


@pytest.fixture
def zap(StakingRewardsZap, gov, registry):
    zap = gov.deploy(StakingRewardsZap, registry.address)
    yield zap


@pytest.fixture
def yvdai_pool(StakingRewardsMulti, gov, yvdai, zap):
    yvdai_pool = gov.deploy(
        StakingRewardsMulti,
        gov.address,
        yvdai.address,
        zap.address,
    )
    yield yvdai_pool


@pytest.fixture
def yvmkusd_pool(StakingRewardsMulti, gov, registry, yvmkusd, zap):
    yvmkusd_pool = gov.deploy(
        StakingRewardsMulti,
        gov.address,
        yvmkusd.address,
        zap.address,
    )
    yield yvmkusd_pool


@pytest.fixture(scope="session")
def RELATIVE_APPROX():
    yield 1e-12
