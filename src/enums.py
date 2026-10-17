"""Controlled vocabularies. Every state set from the spec lives here so models,
schemas, business logic, and the UI share one source of truth.
"""
from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:  # nicer display in Streamlit / logs
        return self.value


class FitLevel(StrEnum):
    STRONG = "Strong"
    MODERATE = "Moderate"
    WEAK = "Weak"
    UNKNOWN = "Unknown"


class CompanyClassification(StrEnum):
    CORE = "Core ICP"
    SECONDARY = "Secondary ICP"
    MONITOR = "Monitor"
    REJECT = "Reject"


class CompanyStage(StrEnum):
    RESEARCHING = "Researching"
    ICP_APPROVED = "ICP Approved"
    ACCESS_CONFIRMED = "Access Confirmed"
    READY_FOR_ENGAGEMENT = "Ready for Engagement"
    ENGAGING = "Engaging"
    CONVERSATION_STARTED = "Conversation Started"
    LEAD_CREATED = "Lead Created"
    COMMERCIAL_NEED_CONFIRMED = "Commercial Need Confirmed"
    QUALIFIED_OPPORTUNITY = "Qualified Opportunity"
    CALL_BOOKED = "Call Booked"
    PROPOSAL = "Proposal"
    WON = "Won"
    LOST = "Lost"
    MONITOR = "Monitor"
    REJECT = "Reject"


class RelationshipStage(StrEnum):
    RESEARCHED = "Researched"
    OBSERVING = "Observing"
    ENGAGED = "Engaged"
    FAMILIAR = "Familiar"
    CONNECTED = "Connected"
    CONVERSATION_ACTIVE = "Conversation Active"
    LEAD = "Lead"
    COMMERCIAL_NEED_CONFIRMED = "Commercial Need Confirmed"
    QUALIFIED_OPPORTUNITY = "Qualified Opportunity"
    CLIENT = "Client"
    REFERRAL_PARTNER = "Referral Partner"
    DORMANT = "Dormant"
    DISQUALIFIED = "Disqualified"


class NetworkQuality(StrEnum):
    UNKNOWN = "Unknown"
    WEAK_AWARENESS = "Weak Awareness"
    RECOGNIZES_ME = "Recognizes Me"
    FAMILIAR = "Familiar"
    CONNECTED = "Connected"
    ACTIVE_RELATIONSHIP = "Active Relationship"
    TRUSTED_RELATIONSHIP = "Trusted Relationship"
    REFERRAL_RELATIONSHIP = "Referral Relationship"


class PersonStatus(StrEnum):
    ACTIVE = "Active"
    MONITOR = "Monitor"
    DORMANT = "Dormant"
    DISQUALIFIED = "Disqualified"


class ExternalSupportLabel(StrEnum):
    OBSERVED = "Observed"
    PLAUSIBLE = "Plausible"
    UNSUPPORTED = "Unsupported"
    UNKNOWN = "Unknown"


class RoleConflict(StrEnum):
    LOW = "Low"
    MANAGEABLE = "Manageable"
    HIGH = "High"
    UNKNOWN = "Unknown"


class EvidenceClassification(StrEnum):
    CONFIRMED_FACT = "Confirmed Fact"
    OBSERVED_BEHAVIOUR = "Observed Behaviour"
    DERIVED_METRIC = "Derived Metric"
    INFERENCE = "Inference"
    HYPOTHESIS = "Hypothesis"
    UNKNOWN = "Unknown"
    UNSUPPORTED_ASSUMPTION = "Unsupported Assumption"


class ActivityType(StrEnum):
    POST = "Post"
    COMMENT = "Comment"
    REPOST = "Repost"
    ARTICLE = "Article"
    PODCAST = "Podcast"
    COMPANY_ANNOUNCEMENT = "Company Announcement"
    OTHER = "Other"


class ActionType(StrEnum):
    FOLLOW = "Follow"
    COMMENT = "Comment"
    CONNECTION_REQUEST = "Connection Request"
    DIRECT_MESSAGE = "Direct Message"
    REPLY = "Reply"
    SHARE_RESOURCE = "Share Resource"
    INTRODUCTION_REQUEST = "Introduction Request"
    INTRODUCTION_MADE = "Introduction Made"
    REFERRAL_GIVEN = "Referral Given"
    CALL_REQUEST = "Call Request"
    MEETING = "Meeting"
    NO_ACTION = "No Action"


class OutcomeType(StrEnum):
    NO_VISIBLE_RESPONSE = "No Visible Response"
    REACTION = "Reaction"
    REPLY = "Reply"
    PROFILE_VIEW = "Profile View"
    FOLLOW = "Follow"
    CONNECTION_ACCEPTED = "Connection Accepted"
    MESSAGE_REPLY = "Message Reply"
    CONVERSATION_STARTED = "Conversation Started"
    INTRODUCTION_RECEIVED = "Introduction Received"
    REFERRAL_RECEIVED = "Referral Received"
    CALL_BOOKED = "Call Booked"
    COMMERCIAL_NEED_CONFIRMED = "Commercial Need Confirmed"
    PROPOSAL_REQUESTED = "Proposal Requested"
    WON = "Won"
    LOST = "Lost"


# Outcomes that are, on their own, a valid commercial signal for creating a lead.
# A reaction, a generic reply, a profile view, a follow, or a bare connection are
# deliberately EXCLUDED — they are not, by themselves, a lead.
LEAD_WORTHY_OUTCOMES = {
    OutcomeType.CONVERSATION_STARTED,
    OutcomeType.INTRODUCTION_RECEIVED,
    OutcomeType.REFERRAL_RECEIVED,
    OutcomeType.COMMERCIAL_NEED_CONFIRMED,
    OutcomeType.CALL_BOOKED,
    OutcomeType.PROPOSAL_REQUESTED,
}

NON_LEAD_OUTCOMES = {
    OutcomeType.NO_VISIBLE_RESPONSE,
    OutcomeType.REACTION,
    OutcomeType.REPLY,
    OutcomeType.PROFILE_VIEW,
    OutcomeType.FOLLOW,
    OutcomeType.CONNECTION_ACCEPTED,
    OutcomeType.MESSAGE_REPLY,
}

# A "meaningful response" for the engagement-response-rate metric: anything
# beyond a passive/mechanical signal (a reaction, a profile view, a bare
# follow are excluded on purpose — see NON_LEAD_OUTCOMES for the same logic
# applied to lead-worthiness).
MEANINGFUL_RESPONSE_OUTCOMES = {
    OutcomeType.REPLY,
    OutcomeType.MESSAGE_REPLY,
    OutcomeType.CONVERSATION_STARTED,
    OutcomeType.INTRODUCTION_RECEIVED,
    OutcomeType.REFERRAL_RECEIVED,
    OutcomeType.CALL_BOOKED,
    OutcomeType.COMMERCIAL_NEED_CONFIRMED,
    OutcomeType.PROPOSAL_REQUESTED,
    OutcomeType.WON,
}


class LeadStage(StrEnum):
    NEW = "New"
    EXPLORING = "Exploring"
    COMMERCIAL_NEED_CONFIRMED = "Commercial Need Confirmed"
    QUALIFIED = "Qualified"
    CONVERTED = "Converted"
    DISQUALIFIED = "Disqualified"


class LeadStatus(StrEnum):
    OPEN = "Open"
    CONVERTED = "Converted"
    DISQUALIFIED = "Disqualified"


class LeadSource(StrEnum):
    LINKEDIN_COMMENT = "LinkedIn Comment"
    LINKEDIN_MESSAGE = "LinkedIn Message"
    CONNECTION = "Connection"
    REFERRAL = "Referral"
    INTRODUCTION = "Introduction"
    EXISTING_NETWORK = "Existing Network"
    INBOUND = "Inbound"
    EVENT = "Event"
    OTHER = "Other"


class OpportunityStage(StrEnum):
    QUALIFICATION = "Qualification"
    DISCOVERY = "Discovery"
    SOLUTION_DEVELOPMENT = "Solution Development"
    PROPOSAL = "Proposal"
    NEGOTIATION = "Negotiation"
    WON = "Won"
    LOST = "Lost"


class TriggerType(StrEnum):
    RETAIL_EXPANSION = "Retail Expansion"
    CHANNEL_EXPANSION = "Channel Expansion"
    PRODUCT_CATEGORY_LAUNCH = "Product Category Launch"
    GEOGRAPHIC_EXPANSION = "Geographic Expansion"
    NEW_COMMERCIAL_LEADERSHIP = "New Commercial Leadership"
    ACQUISITION_COST_PRESSURE = "Acquisition Cost Pressure"
    GROWTH_PLATEAU = "Growth Plateau"
    MARGIN_PRESSURE = "Margin Pressure"
    RESTRUCTURING = "Restructuring"
    NEW_FUNDING = "New Funding"
    MAJOR_PARTNERSHIP = "Major Partnership"
    OPERATIONAL_TRANSFORMATION = "Operational Transformation"
    NONE = "None"


class BuyerRole(StrEnum):
    FOUNDER_CEO = "Founder/CEO/Co-CEO"
    COO = "COO"
    GENERAL_MANAGER = "General Manager"
    VP_SALES_MARKETING = "VP Sales & Marketing"
    OTHER = "Other"


PRIMARY_BUYER_ROLES = {BuyerRole.FOUNDER_CEO}
SECONDARY_BUYER_ROLES = {BuyerRole.COO, BuyerRole.GENERAL_MANAGER, BuyerRole.VP_SALES_MARKETING}


class AuthorityLevel(StrEnum):
    ECONOMIC_BUYER = "Economic Buyer"
    PROBLEM_OWNER = "Problem Owner"
    INFLUENCER = "Influencer"
    UNKNOWN = "Unknown"


class NextAction(StrEnum):
    RESEARCH_MISSING_EVIDENCE = "Research Missing Evidence"
    MONITOR_COMPANY = "Monitor Company"
    MONITOR_PERSON = "Monitor Person"
    WAIT_FOR_RELEVANT_POST = "Wait for Relevant Post"
    FOLLOW_PERSON = "Follow Person"
    COMMENT_ON_CURRENT_POST = "Comment on Current Post"
    REQUEST_CONNECTION = "Request Connection"
    REPLY_TO_INTERACTION = "Reply to Interaction"
    SEND_RELEVANT_INSIGHT = "Send Relevant Insight"
    CONTINUE_CONVERSATION = "Continue Conversation"
    REQUEST_INTRODUCTION = "Request Introduction"
    REQUEST_CALL = "Request Call"
    PREPARE_DISCOVERY = "Prepare Discovery"
    SEND_PROPOSAL = "Send Proposal"
    FOLLOW_UP = "Follow Up"
    RE_ENGAGE = "Re-engage"
    DISQUALIFY = "Disqualify"
    NO_ACTION = "No Action"


class TimelineEventType(StrEnum):
    PERSON_DISCOVERED = "Person discovered"
    POST_OBSERVED = "Post observed"
    FOLLOWED = "Followed"
    COMMENT_POSTED = "Comment posted"
    COMMENT_LIKED = "Comment liked"
    COMMENT_REPLY_RECEIVED = "Comment reply received"
    PROFILE_VIEW = "Profile view"
    CONNECTION_REQUEST_SENT = "Connection request sent"
    CONNECTION_ACCEPTED = "Connection accepted"
    MESSAGE_SENT = "Message sent"
    MESSAGE_REPLY_RECEIVED = "Message reply received"
    CONVERSATION_STARTED = "Conversation started"
    LEAD_CREATED = "Lead created"
    CALL_REQUESTED = "Call requested"
    CALL_BOOKED = "Call booked"
    COMMERCIAL_NEED_IDENTIFIED = "Commercial need identified"
    OPPORTUNITY_QUALIFIED = "Opportunity qualified"
    PROPOSAL_SENT = "Proposal sent"
    WON = "Won"
    LOST = "Lost"
    INTRODUCTION_RECEIVED = "Introduction received"
    REFERRAL_RECEIVED = "Referral received"
    MANUAL_NOTE = "Manual note"
    NO_RESPONSE = "No response"
    STAGE_CHANGE = "Stage change"
