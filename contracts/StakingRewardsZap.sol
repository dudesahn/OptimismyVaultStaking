// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.8.18;

import "@openzeppelin_new/contracts/access/Ownable.sol";
import "@openzeppelin_new/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin_new/contracts/token/ERC20/utils/SafeERC20.sol";

interface IVault is IERC20 {
    function asset() external view returns (address);

    function deposit(uint256, address) external returns (uint256);
}

interface IStakingRewards {
    function stakeFor(address recipient, uint256 amount) external;
}

interface IRegistry {
    function stakingPool(address vault) external view returns (address);
}

contract StakingRewardsZap is Ownable {
    using SafeERC20 for IERC20;

    /* ========== STATE VARIABLES ========== */

    /// @notice Address of our staking pool registry.
    address public stakingPoolRegistry;

    /* ========== EVENTS ========== */

    event ZapIn(
        address indexed user,
        address indexed targetVault,
        uint256 amount
    );

    event UpdatedPoolRegistry(address registry);
    event Recovered(address token, uint256 amount);

    /* ========== MUTATIVE FUNCTIONS ========== */

    function zapIn(address _targetVault, uint256 _underlyingAmount)
        external
        returns (uint256)
    {
        // check what our address is, make sure it's not zero
        IStakingRewards _vaultStakingPool =
            IStakingRewards(
                IRegistry(stakingPoolRegistry).stakingPool(_targetVault)
            );
        require(
            address(_vaultStakingPool) != address(0),
            "staking pool does not exist"
        );

        // get our underlying token
        IERC20 underlying = IERC20(IVault(_targetVault).asset());

        // transfer to zap and deposit underlying to vault, but first check our approvals and store starting amount
        uint256 beforeAmount = underlying.balanceOf(address(this));

        underlying.safeTransferFrom(
            msg.sender,
            address(this),
            _underlyingAmount
        );

        // Check allowance to the vault.
        _checkAllowance(_targetVault, address(underlying), _underlyingAmount);
        // deposit only our underlying amount, make sure deposit worked
        uint256 toStake =
            IVault(_targetVault).deposit(_underlyingAmount, address(this));

        // this shouldn't be reached thanks to vault checks, but leave it in case vault code changes
        require(
            underlying.balanceOf(address(this)) == beforeAmount && toStake > 0,
            "deposit failed"
        );

        // make sure we have approved the staking pool, as they can be added/updated at any time
        _checkAllowance(address(_vaultStakingPool), _targetVault, toStake);

        // stake for our user, return the amount we staked
        _vaultStakingPool.stakeFor(msg.sender, toStake);
        emit ZapIn(msg.sender, _targetVault, toStake);
        return toStake;
    }

    function _checkAllowance(
        address _contract,
        address _token,
        uint256 _amount
    ) internal {
        if (IERC20(_token).allowance(address(this), _contract) < _amount) {
            IERC20(_token).approve(_contract, 0);
            IERC20(_token).approve(_contract, type(uint256).max);
        }
    }

    /// @notice Use this in case someone accidentally sends tokens here.
    function recoverERC20(address tokenAddress, uint256 tokenAmount)
        external
        onlyOwner
    {
        IERC20(tokenAddress).safeTransfer(owner(), tokenAmount);
        emit Recovered(tokenAddress, tokenAmount);
    }

    /* ========== SETTERS ========== */

    /**
    @notice Set the registry for pulling our staking pools.
    @dev Throws if caller is not owner.
    @param _stakingPoolRegistry The address to use as pool registry.
     */
    function setPoolRegistry(address _stakingPoolRegistry) external onlyOwner {
        stakingPoolRegistry = _stakingPoolRegistry;
        emit UpdatedPoolRegistry(_stakingPoolRegistry);
    }
}
