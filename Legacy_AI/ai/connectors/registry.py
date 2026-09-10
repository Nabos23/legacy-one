from ai.connectors.gmail import GmailConnector
from ai.connectors.slack import SlackConnector
from ai.connectors.google_drive import GoogleDriveConnector
from ai.connectors.google_calendar import GoogleCalendarConnector
from ai.connectors.google_sheets import GoogleSheetsConnector
from ai.connectors.outlook import OutlookConnector
from ai.connectors.teams import TeamsConnector
from ai.connectors.onedrive import OneDriveConnector
from ai.connectors.dropbox import DropboxConnector
from ai.connectors.notion import NotionConnector
from ai.connectors.hubspot import HubSpotConnector
from ai.connectors.airtable import AirtableConnector
from ai.connectors.telegram import TelegramConnector
from ai.connectors.discord import DiscordConnector
from ai.connectors.salesforce import SalesforceConnector
from ai.connectors.zendesk import ZendeskConnector
from ai.connectors.box import BoxConnector
from ai.connectors.sharepoint import SharePointConnector
from ai.connectors.google_cloud_storage import GoogleCloudStorageConnector
from ai.connectors.aws_s3 import AWSS3Connector
from ai.connectors.whatsapp import WhatsAppConnector
from ai.connectors.jira import JiraConnector
from ai.connectors.github import GitHubConnector
from ai.connectors.stripe import StripeConnector
from ai.connectors.twilio import TwilioConnector
from ai.connectors.asana import AsanaConnector
from ai.connectors.monday import MondayConnector
from ai.connectors.quickbooks import QuickBooksConnector
from ai.connectors.docusign import DocuSignConnector
from ai.connectors.intercom import IntercomConnector
from ai.connectors.pipedrive import PipedriveConnector
from ai.connectors.servicenow import ServiceNowConnector
from ai.connectors.google_analytics import GoogleAnalyticsConnector
from ai.connectors.figma import FigmaConnector
from ai.connectors.shopify import ShopifyConnector
from ai.connectors.woocommerce import WooCommerceConnector
from ai.connectors.confluence import ConfluenceConnector
from ai.connectors.upwork import UpworkConnector
from ai.connectors.fiverr import FiverrConnector
from ai.connectors.xero import XeroConnector
from ai.connectors.paypal import PaypalConnector
from ai.connectors.freshbooks import FreshBooksConnector
from ai.connectors.wave import WaveConnector
from ai.connectors.fitbit import FitbitConnector
from ai.connectors.strava import StravaConnector
from ai.connectors.withings import WithingsConnector
from ai.connectors.sentry import SentryConnector
from ai.connectors.gitlab import GitlabConnector
from ai.connectors.linear import LinearConnector
from ai.connectors.pagerduty import PagerdutyConnector
from ai.connectors.zoom import ZoomConnector
from ai.connectors.mailchimp import MailchimpConnector
from ai.connectors.sendgrid import SendgridConnector
from ai.connectors.linkedin import LinkedInConnector
from ai.connectors.twitter import TwitterConnector
from ai.connectors.facebook import FacebookConnector
from ai.connectors.instagram import InstagramConnector
from ai.connectors.tiktok import TikTokConnector
from ai.connectors.zoho_crm import ZohoCrmConnector
from ai.connectors.bamboohr import BamboohrConnector
from ai.connectors.greenhouse import GreenhouseConnector
from ai.connectors.datadog import DatadogConnector
from ai.connectors.calendly import CalendlyConnector
from ai.connectors.word import WordConnector
from ai.connectors.excel import ExcelConnector
from ai.connectors.clickup import ClickUpConnector
from ai.connectors.google_meet import GoogleMeetConnector

CONNECTOR_CLASS_MAP: dict[str, type] = {
    "gmail": GmailConnector,
    "slack": SlackConnector,
    "google-drive": GoogleDriveConnector,
    "google-calendar": GoogleCalendarConnector,
    "google-sheets": GoogleSheetsConnector,
    "google-meet": GoogleMeetConnector,
    "outlook": OutlookConnector,
    "teams": TeamsConnector,
    "onedrive": OneDriveConnector,
    "dropbox": DropboxConnector,
    "notion": NotionConnector,
    "hubspot": HubSpotConnector,
    "airtable": AirtableConnector,
    "telegram": TelegramConnector,
    "discord": DiscordConnector,
    "salesforce": SalesforceConnector,
    "zendesk": ZendeskConnector,
    "box": BoxConnector,
    "sharepoint": SharePointConnector,
    "google-cloud-storage": GoogleCloudStorageConnector,
    "aws-s3": AWSS3Connector,
    "whatsapp": WhatsAppConnector,
    "jira": JiraConnector,
    "github": GitHubConnector,
    "stripe": StripeConnector,
    "twilio": TwilioConnector,
    "asana": AsanaConnector,
    "monday": MondayConnector,
    "clickup": ClickUpConnector,
    "quickbooks": QuickBooksConnector,
    "docusign": DocuSignConnector,
    "intercom": IntercomConnector,
    "pipedrive": PipedriveConnector,
    "servicenow": ServiceNowConnector,
    "google-analytics": GoogleAnalyticsConnector,
    "figma": FigmaConnector,
    "shopify": ShopifyConnector,
    "woocommerce": WooCommerceConnector,
    "confluence": ConfluenceConnector,
    "upwork": UpworkConnector,
    "fiverr": FiverrConnector,
    "xero": XeroConnector,
    "paypal": PaypalConnector,
    "freshbooks": FreshBooksConnector,
    "wave": WaveConnector,
    "fitbit": FitbitConnector,
    "strava": StravaConnector,
    "withings": WithingsConnector,
    "sentry": SentryConnector,
    "gitlab": GitlabConnector,
    "linear": LinearConnector,
    "pagerduty": PagerdutyConnector,
    "zoom": ZoomConnector,
    "mailchimp": MailchimpConnector,
    "sendgrid": SendgridConnector,
    "linkedin": LinkedInConnector,
    "twitter": TwitterConnector,
    "facebook": FacebookConnector,
    "instagram": InstagramConnector,
    "tiktok": TikTokConnector,
    "zoho-crm": ZohoCrmConnector,
    "bamboohr": BamboohrConnector,
    "greenhouse": GreenhouseConnector,
    "datadog": DatadogConnector,
    "calendly": CalendlyConnector,
    "word": WordConnector,
    "excel": ExcelConnector,
}
