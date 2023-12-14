// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.8.18;

import "@openzeppelin_new/contracts/access/Ownable.sol";

interface IStakingRewards {
    function stakingToken() external view returns (address);

    function owner() external view returns (address);

    function initialize(
        address _owner,
        address _rewardsDistribution,
        address _rewardsToken,
        address _stakingToken,
        address _zapContract
    ) external;
}

contract StakingRewardsRegistry is Ownable {
    /* ========== STATE VARIABLES ========== */

    /// @notice If a stakingPool exists for a given token, it will be shown here.
    /// @dev Only stakingPools added to this registry will be shown.
    mapping(address => address) public stakingPool;

    /// @notice Tokens that this registry has added stakingPools for.
    address[] public tokens;

    /// @notice Check if an stakingPool exists for a given vault token.
    mapping(address => bool) public isRegistered;

    /// @notice Check if an address is allowed to own stakingPools from this registry.
    mapping(address => bool) public approvedPoolOwner;

    /// @notice Check if a given stakingPool is known to this registry.
    mapping(address => bool) public isStakingPoolEndorsed;

    /// @notice Check if an address can add pools to this registry.
    mapping(address => bool) public poolEndorsers;

    /// @notice Zapper contract to user.
    address public zapper;

    /// @notice Original Staking Rewards contract to clone.
    address public immutable original;

    /* ========== EVENTS ========== */

    event StakingPoolAdded(address indexed token, address indexed stakingPool);
    event ApprovedPoolOwnerUpdated(address governance, bool approved);
    event ApprovedPoolEndorser(address account, bool canEndorse);
    event ZapContractUpdated(address _zapContract);

    constructor(address _originalStaker, address _zapContract) {
        original = _originalStaker;
        zapper = _zapContract;
    }

    /* ========== VIEWS ========== */

    /// @notice The number of tokens with staking pools added to this registry.
    function numTokens() external view returns (uint256) {
        return tokens.length;
    }

    /* ========== CORE FUNCTIONS ========== */

    /**
    @notice
        Add a new staking pool to our registry, for new or existing tokens.
    @dev
        Throws if governance isn't set properly.
        Throws if sender isn't allowed to endorse.
        Throws if replacement is handled improperly.
        Emits a StakingPoolAdded event.
    @param _stakingPool The address of the new staking pool.
    @param _token The token to be deposited into the new staking pool.
    @param _replaceExistingPool If we are replacing an existing staking pool, set this to true.
     */
    function addStakingPool(
        address _stakingPool,
        address _token,
        bool _replaceExistingPool
    ) external {
        // don't let just anyone add to our registry
        require(poolEndorsers[msg.sender], "unauthorized");
        _addStakingPool(_stakingPool, _token, _replaceExistingPool);
    }

    /**
    @notice
        Add a new staking pool to our registry, for new or existing tokens.
    @dev
        Throws if governance isn't set properly.
        Throws if sender isn't allowed to endorse.
        Throws if replacement is handled improperly.
        Emits a StakingPoolAdded event.
    @param _stakingPool The address of the new staking pool.
    @param _token The token to be deposited into the new staking pool.
    @param _replaceExistingPool If we are replacing an existing staking pool, set this to true.
     */
    function _addStakingPool(
        address _stakingPool,
        address _token,
        bool _replaceExistingPool
    ) internal {
        // load up the staking pool contract
        IStakingRewards stakingRewards = IStakingRewards(_stakingPool);

        // check that gov is correct on the staking contract
        address poolGov = stakingRewards.owner();
        require(approvedPoolOwner[poolGov], "not allowed pool owner");

        // make sure we didn't mess up our token/staking pool match
        require(
            stakingRewards.stakingToken() == _token,
            "staking token doesn't match"
        );

        // Make sure we're only using the latest stakingPool in our registry
        if (_replaceExistingPool) {
            require(
                isRegistered[_token] == true,
                "token isn't registered, can't replace"
            );
            address oldPool = stakingPool[_token];
            isStakingPoolEndorsed[oldPool] = false;
            stakingPool[_token] = _stakingPool;
        } else {
            require(
                isRegistered[_token] == false,
                "replace instead, pool already exists"
            );
            stakingPool[_token] = _stakingPool;
            isRegistered[_token] = true;
            tokens.push(_token);
        }

        isStakingPoolEndorsed[_stakingPool] = true;
        emit StakingPoolAdded(_token, _stakingPool);
    }

    /* ========== CLONING ========== */

    event Cloned(address indexed clone);

    /**
     @notice Used for owner to clone an exact copy of this staking pool and add to registry.
     @dev Note that owner will have to call acceptOwnership() to assume ownership of the new staking pool.
     @param _rewardsToken Address of our rewards token.
     @param _stakingToken Address of our staking token.
    */
    function cloneAndAddStakingPool(
        address _rewardsToken,
        address _stakingToken
    ) external onlyOwner returns (address newStakingPool) {
        // Clone new pool.
        newStakingPool = cloneStakingPool(
            owner(),
            owner(),
            _rewardsToken,
            _stakingToken,
            zapper
        );

        // Add to the registry.
        _addStakingPool(
            newStakingPool,
            _stakingToken,
            isRegistered[_stakingToken]
        );
    }

    /**
     @notice Use this to clone an exact copy of this staking pool.
     @dev Note that owner will have to call acceptOwnership() to assume ownership of the new staking pool.
     @param _owner Owner of the new staking contract.
     @param _rewardsDistribution Only this address can call notifyRewardAmount, to add more rewards.
     @param _rewardsToken Address of our rewards token.
     @param _stakingToken Address of our staking token.
     @param _zapContract Address of our zap contract.
    */
    function cloneStakingPool(
        address _owner,
        address _rewardsDistribution,
        address _rewardsToken,
        address _stakingToken,
        address _zapContract
    ) public returns (address newStakingPool) {
        // Copied from https://github.com/optionality/clone-factory/blob/master/contracts/CloneFactory.sol
        bytes20 addressBytes = bytes20(original);
        assembly {
            // EIP-1167 bytecode
            let clone_code := mload(0x40)
            mstore(
                clone_code,
                0x3d602d80600a3d3981f3363d3d373d3d3d363d73000000000000000000000000
            )
            mstore(add(clone_code, 0x14), addressBytes)
            mstore(
                add(clone_code, 0x28),
                0x5af43d82803e903d91602b57fd5bf30000000000000000000000000000000000
            )
            newStakingPool := create(0, clone_code, 0x37)
        }

        IStakingRewards(newStakingPool).initialize(
            _owner,
            _rewardsDistribution,
            _rewardsToken,
            _stakingToken,
            _zapContract
        );

        emit Cloned(newStakingPool);
    }

    /* ========== SETTERS ========== */

    /**
    @notice Set the ability of an address to endorse staking pools.
    @dev Throws if caller is not owner.
    @param _addr The address to approve or deny access.
    @param _approved Allowed to endorse
     */
    function setPoolEndorsers(address _addr, bool _approved)
        external
        onlyOwner
    {
        poolEndorsers[_addr] = _approved;
        emit ApprovedPoolEndorser(_addr, _approved);
    }

    /**
    @notice Set the staking pool owners
    @dev Throws if caller is not owner.
    @param _addr The address to approve or deny access.
    @param _approved Allowed to own staking pools
     */
    function setApprovedPoolOwner(address _addr, bool _approved)
        external
        onlyOwner
    {
        approvedPoolOwner[_addr] = _approved;
        emit ApprovedPoolOwnerUpdated(_addr, _approved);
    }

    /// @notice Set our zap contract.
    /// @dev May only be called by owner, and can't be set to zero address.
    /// @param _zapContract Address of the new zap contract.
    function setZapContract(address _zapContract) external onlyOwner {
        require(_zapContract != address(0), "no zero address");
        zapper = _zapContract;
        emit ZapContractUpdated(_zapContract);
    }
}
