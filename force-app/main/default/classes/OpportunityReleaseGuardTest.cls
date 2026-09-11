@IsTest
private class OpportunityReleaseGuardTest {
    @IsTest
    static void boundaryAtTwentyDoesNotRequireApproval() {
        System.assertEquals(false, OpportunityReleaseGuard.requiresFinanceApproval(20, 'Closed Won'));
    }

    @IsTest
    static void aboveTwentyRequiresApproval() {
        System.assertEquals(true, OpportunityReleaseGuard.requiresFinanceApproval(20.01, 'Closed Won'));
    }

    @IsTest
    static void nonClosedWonDoesNotRequireApproval() {
        System.assertEquals(false, OpportunityReleaseGuard.requiresFinanceApproval(50, 'Proposal/Price Quote'));
    }
}
