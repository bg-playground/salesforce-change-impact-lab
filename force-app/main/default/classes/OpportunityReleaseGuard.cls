public with sharing class OpportunityReleaseGuard {
    public static Boolean requiresFinanceApproval(Decimal discountPercent, String stageName) {
        return stageName == 'Closed Won' && discountPercent != null && discountPercent > 20;
    }
}
