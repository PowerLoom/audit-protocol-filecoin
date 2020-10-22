pragma solidity ^0.5.17;
pragma experimental ABIEncoderV2;

contract AuditRecordStore {
    struct PayloadRecord {
        bytes32 payloadHash;
        uint256 timestamp;
    }

    event RecordAppended(bytes32 tokenHash, bytes32 recordHash, uint256 indexed timestamp);

    mapping(bytes32 => PayloadRecord[]) private tokenHashesToRecords;


    constructor() public {

    }

    function commitRecordHash(bytes32 payloadHash, bytes32 apiKeyHash) public {
        PayloadRecord memory a = PayloadRecord(payloadHash, now);
        tokenHashesToRecords[tokenHash].push(a);
        emit RecordAppended(tokenHash, payloadHash, now);
    }

    function getTokenRecordLogs(bytes32 tokenHash) public view returns (PayloadRecord[] memory recordLogs) {
        return tokenHashesToRecords[tokenHash];
    }
}