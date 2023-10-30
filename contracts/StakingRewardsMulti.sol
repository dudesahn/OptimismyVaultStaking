// SPDX-License-Identifier: AGPL-3.0
pragma solidity ^0.5.16;

import "@openzeppelin/contracts/math/SafeMath.sol";
import "@openzeppelin/contracts/token/ERC20/ERC20Detailed.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

// Inheritance
import "./interfaces/IStakingRewards.sol";
import "./RewardsDistributionRecipient.sol";
import "./Pausable.sol";

// https://docs.synthetix.io/contracts/source/contracts/stakingrewards
/**
 * @title Yearn Vault Staking MultiRewards
 * @author YearnFi
 * @notice Modified staking contract that allows users to deposit vault tokens and receive multiple different reward
 *  tokens, and also allows depositing straight from vault underlying via the StakingRewardsZap.
 *
 *  This work builds on that of Synthetix (StakingRewards.sol) and CurveFi (MultiRewards.sol).
 */
contract StakingRewardsMulti is IStakingRewards, ReentrancyGuard, Pausable {
    using SafeMath for uint256;
    using SafeERC20 for IERC20;

    /* ========== STATE VARIABLES ========== */

    struct Reward {
        address rewardsDistributor;
        /// @notice The duration of our rewards distribution for staking, default is 7 days.
        uint256 rewardsDuration;
        /// @notice The end (timestamp) of our current or most recent reward period.
        uint256 periodFinish;
        /// @notice The distribution rate of rewardsToken per second.
        uint256 rewardRate;
        /**
         * @notice The last time rewards were updated, triggered by updateReward() or notifyRewardAmount().
         * @dev  Will be the timestamp of the update or the end of the period, whichever is earlier.
         */
        uint256 lastUpdateTime;
        /**
         * @notice The most recent stored amount for rewardPerToken().
         * @dev Updated every time anyone calls the updateReward() modifier.
         */
        uint256 rewardPerTokenStored;
    }

    /// @notice The address of our rewards token => reward info.
    mapping(address => Reward) public rewardData;

    address[] public rewardTokens;

    /// @notice The address of our zap contract, allows depositing to vault and staking in one transaction.
    address public zapContract;

    /**
     * @notice Bool for if this staking contract is shut down and rewards have been swept out.
     * @dev Can only be performed at least 90 days after final reward period ends.
     */
    bool public isRetired;

    /**
     * @notice The amount of rewards allocated to a user per whole token staked.
     * @dev Note that this is not the same as amount of rewards claimed. user -> reward token -> amount
     */
    mapping(address => mapping(address => uint256))
        public userRewardPerTokenPaid;

    /// @notice The amount of unclaimed rewards an account is owed.
    mapping(address => mapping(address => uint256)) public rewards;

    // private vars, use view functions to see these
    uint256 private _totalSupply;
    mapping(address => uint256) private _balances;

    /* ========== CONSTRUCTOR ========== */

    constructor(
        address _owner,
        address _stakingToken,
        address _zapContract
    ) public Owned(_owner) {
        stakingToken = IERC20(_stakingToken);
        zapContract = _zapContract;
    }

    /* ========== VIEWS ========== */

    /// @notice The total tokens staked in this contract.
    function totalSupply() external view returns (uint256) {
        return _totalSupply;
    }

    /// @notice The balance a given user has staked.
    function balanceOf(address _account) external view returns (uint256) {
        return _balances[_account];
    }

    /// @notice Either the current timestamp or end of the most recent period.
    function lastTimeRewardApplicable(address _rewardsToken)
        public
        view
        returns (uint256)
    {
        return
            Math.min(block.timestamp, rewardData[_rewardsToken].periodFinish);
    }

    /// @notice Reward paid out per whole token.
    function rewardPerToken(address _rewardsToken)
        public
        view
        returns (uint256)
    {
        if (_totalSupply == 0) {
            return rewardData[_rewardsToken].rewardPerTokenStored;
        }

        if (isRetired) {
            return 0;
        }

        return
            rewardData[_rewardsToken].rewardPerTokenStored.add(
                lastTimeRewardApplicable(_rewardsToken)
                    .sub(rewardData[_rewardsToken].lastUpdateTime)
                    .mul(rewardData[_rewardsToken].rewardRate)
                    .mul(1e18)
                    .div(_totalSupply)
            );
    }

    /**
     * @notice Amount of reward token pending claim by an account.
     * @param _account Amount of vault tokens to deposit.
     * @param _rewardsToken Amount of vault tokens to deposit.
     */
    function earned(address _account, address _rewardsToken)
        public
        view
        returns (uint256)
    {
        if (isRetired) {
            return 0;
        }

        return
            _balances[_account]
                .mul(
                rewardPerToken(_rewardsToken).sub(
                    userRewardPerTokenPaid[_account][_rewardsToken]
                )
            )
                .div(1e18)
                .add(rewards[_account][_rewardsToken]);
    }

    function getRewardForDuration(address _rewardsToken)
        external
        view
        returns (uint256)
    {
        return
            rewardData[_rewardsToken].rewardRate.mul(
                rewardData[_rewardsToken].rewardsDuration
            );
    }

    /* ========== MUTATIVE FUNCTIONS ========== */

    /**
     * @notice Deposit vault tokens to the staking pool.
     * @dev Can't stake zero.
     * @param _amount Amount of vault tokens to deposit.
     */
    function stake(uint256 _amount)
        external
        nonReentrant
        notPaused
        updateReward(msg.sender)
    {
        require(_amount > 0, "Cannot stake 0");
        require(!isRetired, "Staking pool is retired");
        _totalSupply = _totalSupply.add(_amount);
        _balances[msg.sender] = _balances[msg.sender].add(_amount);
        stakingToken.safeTransferFrom(msg.sender, address(this), _amount);
        emit Staked(msg.sender, _amount);
    }

    /**
     * @notice Deposit vault tokens for specified recipient.
     * @dev Can't stake zero, can only be used by zap contract.
     * @param _recipient Address of user these vault tokens are being staked for.
     * @param _amount Amount of vault token to deposit.
     */
    function stakeFor(address _recipient, uint256 _amount)
        external
        nonReentrant
        notPaused
        updateReward(_recipient)
    {
        require(msg.sender == zapContract, "Only zap contract");
        require(_amount > 0, "Cannot stake 0");
        require(!isRetired, "Staking pool is retired");
        _totalSupply = _totalSupply.add(_amount);
        _balances[_recipient] = _balances[_recipient].add(_amount);
        stakingToken.safeTransferFrom(msg.sender, address(this), _amount);
        emit StakedFor(_recipient, _amount);
    }

    /**
     * @notice Withdraw vault tokens from the staking pool.
     * @dev Can't withdraw zero. If trying to claim, call getReward() instead.
     * @param _amount Amount of vault tokens to withdraw.
     */
    function withdraw(uint256 _amount)
        public
        nonReentrant
        updateReward(msg.sender)
    {
        require(_amount > 0, "Cannot withdraw 0");
        _totalSupply = _totalSupply.sub(_amount);
        _balances[msg.sender] = _balances[msg.sender].sub(_amount);
        stakingToken.safeTransfer(msg.sender, _amount);
        emit Withdrawn(msg.sender, _amount);
    }

    /**
     * @notice Claim any earned reward tokens.
     * @dev Can claim rewards even if no tokens still staked.
     */
    function getReward() public nonReentrant updateReward(msg.sender) {
        for (uint256 i; i < rewardTokens.length; i++) {
            address _rewardsToken = rewardTokens[i];
            uint256 reward = rewards[msg.sender][_rewardsToken];
            if (reward > 0) {
                rewards[msg.sender][_rewardsToken] = 0;
                IERC20(_rewardsToken).safeTransfer(msg.sender, reward);
                emit RewardPaid(msg.sender, _rewardsToken, reward);
            }
        }
    }

    /**
     * @notice Unstake all of the sender's tokens and claim any outstanding rewards.
     */
    function exit() external {
        withdraw(_balances[msg.sender]);
        getReward();
    }

    /* ========== RESTRICTED FUNCTIONS ========== */

    /**
     * @notice Notify staking contract that it has more reward to account for.
     * @dev Reward tokens must be sent to contract before notifying. May only be called
     *  by rewards distribution role.
     * @param _rewardAmount Amount of reward tokens to add.
     */
    function notifyRewardAmount(address _rewardsToken, uint256 _rewardAmount)
        external
        updateReward(address(0))
    {
        require(rewardData[_rewardsToken].rewardsDistributor == msg.sender);
        // handle the transfer of reward tokens via `transferFrom` to reduce the number
        // of transactions required and ensure correctness of the reward amount
        IERC20(_rewardsToken).safeTransferFrom(
            msg.sender,
            address(this),
            _rewardAmount
        );

        if (block.timestamp >= rewardData[_rewardsToken].periodFinish) {
            rewardData[_rewardsToken].rewardRate = _rewardAmount.div(
                rewardData[_rewardsToken].rewardsDuration
            );
        } else {
            uint256 remaining =
                rewardData[_rewardsToken].periodFinish.sub(block.timestamp);
            uint256 leftover =
                remaining.mul(rewardData[_rewardsToken].rewardRate);
            rewardData[_rewardsToken].rewardRate = _rewardAmount
                .add(leftover)
                .div(rewardData[_rewardsToken].rewardsDuration);
        }

        // Ensure the provided reward amount is not more than the balance in the contract.
        // This keeps the reward rate in the right range, preventing overflows due to
        // very high values of rewardRate in the earned and rewardsPerToken functions;
        // Reward + leftover must be less than 2^256 / 10^18 to avoid overflow.
        uint256 balance = IERC20(_rewardsToken).balanceOf(address(this));
        require(
            rewardData[_rewardsToken].rewardRate <=
                balance.div(rewardData[_rewardsToken].rewardsDuration),
            "Provided reward too high"
        );

        rewardData[_rewardsToken].lastUpdateTime = block.timestamp;
        rewardData[_rewardsToken].periodFinish = block.timestamp.add(
            rewardData[_rewardsToken].rewardsDuration
        );
        emit RewardAdded(_rewardAmount);
    }

    /**
     * @notice Sweep out tokens accidentally sent here.
     * @dev May only be called by owner.
     * @param _tokenAddress Address of token to sweep.
     * @param _tokenAmount Amount of tokens to sweep.
     */
    function recoverERC20(address _tokenAddress, uint256 _tokenAmount)
        external
        onlyOwner
    {
        require(
            _tokenAddress != address(stakingToken),
            "Cannot withdraw the staking token"
        );

        // can only recover rewardsToken 90 days after end
        if (_tokenAddress == address(rewardsToken)) {
            require(
                block.timestamp > periodFinish + 90 days,
                "wait 90 days to sweep leftover rewards"
            );

            // if we do this, automatically sweep all rewardsToken
            _tokenAmount = rewardsToken.balanceOf(address(this));

            // retire this staking contract, this wipes all rewards but still allows all users to withdraw
            isRetired = true;
        }

        IERC20(_tokenAddress).safeTransfer(owner, _tokenAmount);
        emit Recovered(_tokenAddress, _tokenAmount);
    }

    /**
     * @notice Set the duration of our rewards period.
     * @dev May only be called by owner, and must be done after most recent period ends.
     * @param _rewardsDuration New length of period in seconds.
     */
    function setRewardsDuration(address _rewardsToken, uint256 _rewardsDuration)
        external
    {
        require(
            block.timestamp > rewardData[_rewardsToken].periodFinish,
            "Reward period still active"
        );
        require(rewardData[_rewardsToken].rewardsDistributor == msg.sender);
        require(_rewardsDuration > 0, "Reward duration must be non-zero");
        rewardData[_rewardsToken].rewardsDuration = _rewardsDuration;
        emit RewardsDurationUpdated(
            _rewardsToken,
            rewardData[_rewardsToken].rewardsDuration
        );
    }

    /**
     * @notice Set our zap contract.
     * @dev May only be called by owner, and can't be set to zero address.
     * @param _zapContract Address of the new zap contract.
     */
    function setZapContract(address _zapContract) external onlyOwner {
        require(_zapContract != address(0), "no zero address");
        zapContract = _zapContract;
        emit ZapContractUpdated(_zapContract);
    }

    function setRewardsDistributor(
        address _rewardsToken,
        address _rewardsDistributor
    ) external onlyOwner {
        rewardData[_rewardsToken].rewardsDistributor = _rewardsDistributor;
    }

    function addReward(
        address _rewardsToken,
        address _rewardsDistributor,
        uint256 _rewardsDuration
    ) public onlyOwner {
        require(rewardData[_rewardsToken].rewardsDuration == 0);
        rewardTokens.push(_rewardsToken);
        rewardData[_rewardsToken].rewardsDistributor = _rewardsDistributor;
        rewardData[_rewardsToken].rewardsDuration = _rewardsDuration;
    }

    /* ========== MODIFIERS ========== */

    modifier updateReward(address _account) {
        for (uint256 i; i < rewardTokens.length; i++) {
            address token = rewardTokens[i];
            rewardData[token].rewardPerTokenStored = rewardPerToken(token);
            rewardData[token].lastUpdateTime = lastTimeRewardApplicable(token);
            if (_account != address(0)) {
                rewards[_account][token] = earned(_account, token);
                userRewardPerTokenPaid[_account][token] = rewardData[token]
                    .rewardPerTokenStored;
            }
        }
        _;
    }

    /* ========== EVENTS ========== */

    event RewardAdded(uint256 reward);
    event Staked(address indexed user, uint256 amount);
    event StakedFor(address indexed user, uint256 amount);
    event Withdrawn(address indexed user, uint256 amount);
    event RewardPaid(
        address indexed user,
        address indexed rewardsToken,
        uint256 reward
    );
    event RewardsDurationUpdated(address token, uint256 newDuration);
    event ZapContractUpdated(address _zapContract);
    event Recovered(address token, uint256 amount);
}
