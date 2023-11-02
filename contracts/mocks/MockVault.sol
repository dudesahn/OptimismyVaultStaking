pragma solidity 0.8.18;

import {
    ERC4626,
    ERC20,
    IERC20Metadata
} from "@openzeppelin_new/contracts/token/ERC20/extensions/ERC4626.sol";

contract MockVault is ERC4626 {
    uint256 public depositLimit = type(uint256).max;

    constructor(address _asset)
        ERC4626(IERC20Metadata(_asset))
        ERC20("test vault", "tsVault")
    {}

    function setDepositLimit(uint256 _limit) external {
        depositLimit = _limit;
    }

    function maxDeposit(address) public view override returns (uint256) {
        return depositLimit;
    }
}
