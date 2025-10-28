# publications/serializers.py
from rest_framework import serializers

from .models import Publication, Notification, SupportTicket, SupportMessage


class PublicationSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.full_name', read_only=True)
    type_display = serializers.CharField(source='get_publication_type_display', read_only=True)
    audience_display = serializers.CharField(source='get_audience_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    absolute_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Publication
        fields = [
            'id', 'title', 'content', 'excerpt', 'publication_type', 'type_display',
            'audience', 'audience_display', 'status', 'status_display', 'target_agencies',
            'target_users', 'is_active', 'is_featured', 'is_pinned', 'start_date',
            'end_date', 'priority', 'image', 'attachment', 'action_url', 'action_text',
            'view_count', 'click_count', 'share_count', 'author', 'author_name',
            'meta_title', 'meta_description', 'slug', 'absolute_url', 'created', 'updated'
        ]
        read_only_fields = ['slug', 'view_count', 'click_count', 'share_count']


class PublicationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publication
        fields = [
            'title', 'content', 'excerpt', 'publication_type', 'audience',
            'target_agencies', 'target_users', 'is_featured', 'is_pinned',
            'start_date', 'end_date', 'priority', 'image', 'attachment',
            'action_url', 'action_text', 'meta_title', 'meta_description'
        ]
    
    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)


class NotificationSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    channel_display = serializers.CharField(source='get_channel_display', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'notification_id', 'user', 'user_name', 'title', 'message',
            'notification_type', 'type_display', 'status', 'status_display',
            'channel', 'channel_display', 'related_publication', 'related_reservation',
            'related_parcel', 'related_trip', 'related_support', 'action_url',
            'action_label', 'icon', 'image', 'sent_at', 'read_at', 'dismissed_at',
            'should_send_email', 'should_send_sms', 'should_send_push', 'email_sent',
            'sms_sent', 'push_sent', 'created', 'updated'
        ]
        read_only_fields = ['notification_id']


class SupportTicketSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.full_name', read_only=True)
    agency_name = serializers.CharField(source='agency.name', read_only=True)
    
    class Meta:
        model = SupportTicket
        fields = [
            'id', 'ticket_id', 'user', 'user_name', 'category', 'category_display',
            'status', 'status_display', 'priority', 'priority_display', 'subject',
            'description', 'attachment', 'assigned_to', 'assigned_to_name', 'agency',
            'agency_name', 'response_time', 'resolution_time', 'satisfaction_rating',
            'satisfaction_comment', 'first_response_at', 'resolved_at', 'closed_at',
            'related_reservation', 'related_parcel', 'related_trip', 'created', 'updated'
        ]
        read_only_fields = ['ticket_id']


class SupportMessageSerializer(serializers.ModelSerializer):
    message_type_display = serializers.CharField(source='get_message_type_display', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    
    class Meta:
        model = SupportMessage
        fields = [
            'id', 'ticket', 'user', 'user_name', 'message', 'message_type',
            'message_type_display', 'is_system', 'is_internal', 'is_first_response',
            'attachment', 'read_by_customer', 'read_by_agent', 'created', 'updated'
        ]