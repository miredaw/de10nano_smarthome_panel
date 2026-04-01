#!/usr/bin/env python3
"""
Custom MQTT Broker for IoT Smart Home Monitor
Uses Mosquitto-compatible broker with authentication
"""

import asyncio
import logging
from hbmqtt.broker import Broker
from hbmqtt.client import MQTTClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SmartHomeMQTTBroker:
    def __init__(self):
        self.broker = None
        self.config = {
            'listeners': {
                'default': {
                    'type': 'tcp',
                    'bind': f"{os.getenv('MQTT_BROKER_HOST', 'localhost')}:{os.getenv('MQTT_BROKER_PORT', '1883')}"
                }
            },
            'sys_interval': 10,
            'auth': {
                'allow-anonymous': False,
                'password-file': 'passwd.txt',
                'plugins': ['auth_anonymous', 'auth_file']
            },
            'topic-check': {
                'enabled': True,
                'plugins': []
            }
        }
    
    async def start(self):
        """Start the MQTT broker"""
        self.broker = Broker(self.config)
        await self.broker.start()
        logger.info(f"MQTT Broker started on {os.getenv('MQTT_BROKER_HOST')}:{os.getenv('MQTT_BROKER_PORT')}")
    
    async def stop(self):
        """Stop the MQTT broker"""
        if self.broker:
            await self.broker.shutdown()
            logger.info("MQTT Broker stopped")

async def main():
    """Main entry point for the MQTT broker"""
    broker = SmartHomeMQTTBroker()
    
    try:
        await broker.start()
        # Keep the broker running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down broker...")
        await broker.stop()
    except Exception as e:
        logger.error(f"Error running broker: {e}")
        await broker.stop()

if __name__ == '__main__':
    asyncio.run(main())
