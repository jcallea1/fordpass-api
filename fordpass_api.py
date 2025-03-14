import requests
import json
import time
import urllib.parse

class FordPassAPI:
    def __init__(self, username, password, vin):
        self.username = username
        self.password = password
        self.vin = vin
        
        # Token storage
        self.ford_token = None
        self.autonomic_token = None
        self.token_expiration = 0
        
        # Authentication URLs from screenshots
        self.ford_token_url = "https://us-central1-ford-connected-car.cloudfunctions.net/api/auth"
        self.autonomic_token_url = "https://accounts.autonomic.ai/v1/auth/oidc/token"
        
        # API endpoints from screenshots
        self.command_url = "https://api.autonomic.ai/v1/command/vehicles/{vin}/commands"
        self.status_url = "https://api.autonomic.ai/v1/telemetry/sources/fordpass/vehicles/{vin}"
        
        # Client ID and Application ID from the screenshots
        self.client_id = "9fb503e0-715b-47e8-adfd-4b7770f73b"
        self.application_id = "71A3AD0A-CF46-4CCF-B473-FC7FE5BC4592"
        
        # Headers based on screenshots
        self.headers = {
            "Accept": "*/*",
            "User-Agent": "FordPass/2 CFNetwork/1475 Darwin/23.0.0",
            "Accept-Language": "en-US,en;q=0.9",
            "Application-Id": self.application_id
        }
    
    def get_ford_token(self):
        """Get the initial FordPass authentication token"""
        if self.ford_token and time.time() < self.token_expiration:
            return self.ford_token
        
        # Just prepare the authentication data
        auth_data = {
            "username": self.username,
            "password": self.password
        }
        
        headers = self.headers.copy()
        headers["Content-Type"] = "application/json"
        
        try:
            response = requests.post(
                self.ford_token_url,
                headers=headers,
                json=auth_data
            )
            
            if response.status_code == 200:
                data = response.json()
                # Check if status is 200 in the response JSON
                if data.get("status") == 200:
                    self.ford_token = data.get("access_token")
                    # Set a short expiration time since we'll be getting the Autonomic token next
                    self.token_expiration = time.time() + 300  # 5 minutes
                    return self.ford_token
                else:
                    # Extract the message if available
                    message = data.get("message", "Unknown error")
                    raise Exception(f"Ford authentication failed: {message}")
            else:
                raise Exception(f"Ford authentication failed: {response.status_code} - {response.text}")
        except Exception as e:
            raise Exception(f"Ford token request failed: {str(e)}")
    
    def get_autonomic_token(self):
        """Get the Autonomic token using the Ford token"""
        if self.autonomic_token and time.time() < self.token_expiration:
            return self.autonomic_token
        
        # First get Ford token if we don't have it
        ford_token = self.get_ford_token()
        
        # Now get Autonomic token using the token exchange grant type with CORRECT parameters
        auth_data = {
            "subject_token": ford_token,
            "subject_issuer": "fordpass",
            "client_id": "fordpass-prod",  # This is the correct client_id
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "subject_token_type": "urn:ietf:params:oauth:token-type:jwt"
        }
        
        headers = self.headers.copy()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        
        # Convert form data to URL-encoded format
        encoded_data = urllib.parse.urlencode(auth_data)
        
        try:
            response = requests.post(
                self.autonomic_token_url,
                headers=headers,
                data=encoded_data
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.autonomic_token = token_data.get("access_token")
                self.token_expiration = time.time() + token_data.get("expires_in", 3600) - 60
                return self.autonomic_token
            else:
                raise Exception(f"Autonomic authentication failed: {response.status_code} - {response.text}")
        except Exception as e:
            raise Exception(f"Autonomic token request failed: {str(e)}")
        
    def get_auth_token(self):
        """Get the final authentication token to use for API calls"""
        return self.get_autonomic_token()
    
    def execute_command(self, command):
        """Execute a command on the vehicle (lock, unlock, start, stop, etc.)"""
        token = self.get_auth_token()
        
        # If command is 'status', use the status endpoint
        if command == "status":
            return self.get_vehicle_status()
        
        # For other commands, use the command endpoint
        command_endpoint = self.command_url.format(vin=self.vin)
        
        headers = self.headers.copy()
        headers["Authorization"] = f"Bearer {token}"
        headers["Content-Type"] = "application/json"
        
        # JSON payload for the command
        command_data = {
            "command": command
        }
        
        try:
            response = requests.post(
                command_endpoint,
                headers=headers,
                json=command_data
            )
            
            if response.status_code in (200, 202):
                return response.json()
            else:
                raise Exception(f"Command failed: {response.status_code} - {response.text}")
        except Exception as e:
            raise Exception(f"Command execution failed: {str(e)}")
    
    def get_vehicle_status(self):
        """Get vehicle status information and save to file"""
        token = self.get_auth_token()
        
        # Format the status URL with the VIN
        status_endpoint = self.status_url.format(vin=self.vin)
        
        headers = self.headers.copy()
        headers["Authorization"] = f"Bearer {token}"
        
        try:
            response = requests.get(
                status_endpoint,
                headers=headers
            )
            
            if response.status_code == 200:
                status_data = response.json()
                
                # Save to file
                with open("fordpass_status.json", "w") as f:
                    json.dump(status_data, indent=2, fp=f)
                    
                print(f"Status response saved to fordpass_status.json")
                return status_data
            else:
                raise Exception(f"Status request failed: {response.status_code} - {response.text}")
        except Exception as e:
            raise Exception(f"Vehicle status request failed: {str(e)}")
        
    
    def get_battery_status(self):
        """Get comprehensive battery status information"""
        try:
            status = self.get_vehicle_status()
            metrics = status.get("metrics", {})
            
            battery_info = {
                "main_battery_charge": metrics.get("batteryStateOfCharge", {}).get("value"),
                "ev_battery_charge": metrics.get("xevBatteryStateOfCharge", {}).get("value"),
                "ev_battery_actual_charge": metrics.get("xevBatteryActualStateOfCharge", {}).get("value"),
                "ev_battery_range_km": metrics.get("xevBatteryRange", {}).get("value"),
                "ev_battery_range_miles": round((metrics.get("xevBatteryRange", {}).get("value") or 0) * 0.621371),
                "ev_battery_capacity_kwh": metrics.get("xevBatteryCapacity", {}).get("value"),
                "ev_battery_energy_remaining_kwh": metrics.get("xevBatteryEnergyRemaining", {}).get("value"),
                "ev_battery_temperature": metrics.get("xevBatteryTemperature", {}).get("value"),
                "ev_battery_voltage": metrics.get("xevBatteryVoltage", {}).get("value"),
                "ev_battery_performance": metrics.get("xevBatteryPerformanceStatus", {}).get("value"),
                "ev_time_to_full_charge": metrics.get("xevBatteryTimeToFullCharge", {}).get("value")
            }
            
            return battery_info
        except Exception as e:
            return f"Unable to retrieve battery information: {str(e)}"
        
    def get_door_status(self):
        """Get door status information"""
        try:
            status = self.get_vehicle_status()
            metrics = status.get("metrics", {})
            
            # Process door status array
            doors = {}
            for door in metrics.get("doorStatus", []):
                door_id = door.get("vehicleDoor")
                door_value = door.get("value")
                doors[door_id] = door_value
            
            # Process door lock status
            locks = {}
            for lock in metrics.get("doorLockStatus", []):
                lock_id = lock.get("vehicleDoor")
                lock_value = lock.get("value")
                locks[lock_id] = lock_value
            
            # Hood status
            hood = metrics.get("hoodStatus", {}).get("value")
            
            return {
                "doors": doors,
                "locks": locks,
                "hood": hood,
                "alarm": metrics.get("alarmStatus", {}).get("value")
            }
        except Exception as e:
            return f"Unable to retrieve door information: {str(e)}"

    def get_mileage(self):
        """Get the vehicle's current mileage"""
        try:
            status = self.get_vehicle_status()
            metrics = status.get("metrics", {})
            
            odometer_value = metrics.get("odometer", {}).get("value")
                
            if odometer_value is not None:
                miles = round(odometer_value * 0.621371)
                return f"Vehicle has {miles} miles on it."
            else:
                return "Odometer information not available"
        except Exception as e:
            return f"Unable to retrieve mileage information: {str(e)}"
        
    def get_tire_status(self):
        """Get tire pressure and status information"""
        try:
            status = self.get_vehicle_status()
            metrics = status.get("metrics", {})
            
            # Process tire pressure array
            pressures = {}
            for tire in metrics.get("tirePressure", []):
                tire_id = tire.get("vehicleWheel")
                tire_value = tire.get("value")
                tire_placard = tire.get("wheelPlacardFront") or tire.get("wheelPlacardRear")
                pressures[tire_id] = {
                    "pressure": tire_value,
                    "recommended": tire_placard
                }
            
            # Process tire status array
            statuses = {}
            for tire in metrics.get("tirePressureStatus", []):
                tire_id = tire.get("vehicleWheel")
                tire_value = tire.get("value")
                if tire_id:
                    statuses[tire_id] = tire_value
                else:
                    statuses["overall"] = tire_value
            
            return {
                "pressures": pressures,
                "statuses": statuses,
                "system_status": metrics.get("tirePressureSystemStatus", [{}])[0].get("value")
            }
        except Exception as e:
            return f"Unable to retrieve tire information: {str(e)}"

    def get_location(self):
        """Get vehicle location information"""
        try:
            status = self.get_vehicle_status()
            metrics = status.get("metrics", {})
            
            position = metrics.get("position", {}).get("value", {}).get("location", {})
            heading_data = metrics.get("heading", {}).get("value", {})
            compass = metrics.get("compassDirection", {}).get("value")
            
            return {
                "latitude": position.get("lat"),
                "longitude": position.get("lon"),
                "altitude": position.get("alt"),
                "heading_degrees": heading_data.get("heading"),
                "compass_direction": compass,
                "update_time": metrics.get("position", {}).get("updateTime")
            }
        except Exception as e:
            return f"Unable to retrieve location information: {str(e)}"

    def get_window_status(self):
        """Get window position information"""
        try:
            status = self.get_vehicle_status()
            metrics = status.get("metrics", {})
            
            windows = {}
            for window in metrics.get("windowStatus", []):
                window_id = f"{window.get('vehicleWindow')}_{window.get('vehicleSide')}"
                range_data = window.get("value", {}).get("doubleRange", {})
                windows[window_id] = {
                    "lower_bound": range_data.get("lowerBound"),
                    "upper_bound": range_data.get("upperBound")
                }
            
            return windows
        except Exception as e:
            return f"Unable to retrieve window information: {str(e)}"

    def get_climate_status(self):
        """Get climate and temperature information"""
        try:
            status = self.get_vehicle_status()
            metrics = status.get("metrics", {})
            
            outside_temp_c = metrics.get("outsideTemperature", {}).get("value")
            outside_temp_f = outside_temp_c * 9/5 + 32 if outside_temp_c is not None else None
            
            return {
                "outside_temperature_c": outside_temp_c,
                "outside_temperature_f": outside_temp_f,
                "ambient_temp": metrics.get("ambientTemp", {}).get("value"),
                "engine_coolant_temp": metrics.get("engineCoolantTemp", {}).get("value")
            }
        except Exception as e:
            return f"Unable to retrieve climate information: {str(e)}"

    def get_vehicle_info(self):
        """Get general vehicle information"""
        try:
            status = self.get_vehicle_status()
            metrics = status.get("metrics", {})
            
            odometer_km = metrics.get("odometer", {}).get("value")
            odometer_miles = round(odometer_km * 0.621371) if odometer_km is not None else None
            
            return {
                "odometer_km": odometer_km,
                "odometer_miles": odometer_miles,
                "speed": metrics.get("speed", {}).get("value"),
                "ignition_status": metrics.get("ignitionStatus", {}).get("value"),
                "oil_life_remaining": metrics.get("oilLifeRemaining", {}).get("value"),
                "parking_brake_status": metrics.get("parkingBrakeStatus", {}).get("value"),
                "gear_position": metrics.get("gearLeverPosition", {}).get("value"),
                "hybrid_vehicle_mode": metrics.get("hybridVehicleModeStatus", {}).get("value"),
                "display_units": metrics.get("displaySystemOfMeasure", {}).get("value")
            }
        except Exception as e:
            return f"Unable to retrieve vehicle information: {str(e)}"

    def get_warning_indicators(self):
        """Get warning indicator status"""
        try:
            status = self.get_vehicle_status()
            metrics = status.get("metrics", {})
            
            indicators = metrics.get("indicators", {})
            # Filter for active indicators only
            active_indicators = {}
            
            for key, indicator in indicators.items():
                if indicator.get("value") == True:
                    active_indicators[key] = indicator.get("additionalInfo", "")
            
            return active_indicators
        except Exception as e:
            return f"Unable to retrieve warning indicators: {str(e)}"

    def get_ev_charging_status(self):
        """Get EV charging status information"""
        try:
            status = self.get_vehicle_status()
            metrics = status.get("metrics", {})
            
            return {
                "plug_status": metrics.get("xevPlugChargerStatus", {}).get("value"),
                "charger_status": metrics.get("xevBatteryChargeDisplayStatus", {}).get("value"),
                "charger_current_output": metrics.get("xevBatteryChargerCurrentOutput", {}).get("value"),
                "charger_voltage_output": metrics.get("xevBatteryChargerVoltageOutput", {}).get("value"),
                "dc_voltage_output": metrics.get("xevEvseBatteryDcVoltageOutput", {}).get("value"),
                "dc_current_output": metrics.get("xevEvseBatteryDcCurrentOutput", {}).get("value"),
                "charger_type": metrics.get("xevChargeStationPowerType", {}).get("value"),
                "communication_status": metrics.get("xevChargeStationCommunicationStatus", {}).get("value")
            }
        except Exception as e:
            return f"Unable to retrieve EV charging information: {str(e)}"

    def get_trip_info(self):
        """Get trip-related information"""
        try:
            status = self.get_vehicle_status()
            metrics = status.get("metrics", {})
            custom_metrics = metrics.get("customMetrics", {})
            
            # Fix the access to custom metrics
            trip_length = None
            acceleration_score = None
            deceleration_score = None
            cruising_score = None
            
            for key, value in custom_metrics.items():
                if "trip-sum-length" in key:
                    trip_length = value.get("value")
                elif "accumulated-acceleration-coaching-score" in key:
                    acceleration_score = value.get("value")
                elif "accumulated-deceleration-coaching-score" in key:
                    deceleration_score = value.get("value")
                elif "accumulated-vehicle-speed-cruising-coaching-score" in key:
                    cruising_score = value.get("value")
            
            return {
                "trip_length": trip_length,
                "trip_fuel_economy": metrics.get("tripFuelEconomy", {}).get("value"),
                "trip_battery_range_regenerated": metrics.get("tripXevBatteryRangeRegenerated", {}).get("value"),
                "trip_battery_charge_regenerated": metrics.get("tripXevBatteryChargeRegenerated", {}).get("value"),
                "trip_battery_distance": metrics.get("tripXevBatteryDistanceAccumulated", {}).get("value"),
                "acceleration_score": acceleration_score,
                "deceleration_score": deceleration_score,
                "cruising_score": cruising_score
            }
        except Exception as e:
            return f"Unable to retrieve trip information: {str(e)}"

    def get_status_summary(self):
        """Get a comprehensive summary of vehicle status"""
        try:
            # Get all the information
            vehicle_info = self.get_vehicle_info()
            battery_info = self.get_battery_status()
            door_info = self.get_door_status()
            climate_info = self.get_climate_status()
            location_info = self.get_location()
            tire_info = self.get_tire_status()
            
            # Create a readable summary
            summary = {
                "vehicle_status": {
                    "odometer": f"{vehicle_info['odometer_miles']} miles ({vehicle_info['odometer_km']} km)" if vehicle_info['odometer_km'] else "Not available",
                    "ignition": vehicle_info['ignition_status'] or "Not available",
                    "doors_locked": "All Locked" if door_info['locks'].get('ALL_DOORS') == "LOCKED" else "Not All Locked",
                    "alarm": door_info['alarm'] or "Not available"
                },
                "battery_status": {
                    "ev_charge": f"{battery_info['ev_battery_charge']}%" if battery_info['ev_battery_charge'] else "Not available",
                    "range": f"{battery_info['ev_battery_range_miles']} miles ({battery_info['ev_battery_range_km']} km)" if battery_info['ev_battery_range_km'] else "Not available",
                    "time_to_full_charge": f"{battery_info['ev_time_to_full_charge']} minutes" if battery_info['ev_time_to_full_charge'] else "Not available"
                },
                "climate": {
                    "outside_temp": f"{round(climate_info['outside_temperature_f'])}°F ({climate_info['outside_temperature_c']}°C)" if climate_info['outside_temperature_c'] else "Not available"
                },
                "location": {
                    "latitude": location_info['latitude'],
                    "longitude": location_info['longitude']
                },
                "tires": "All Normal" if all(status == "NORMAL" for status in tire_info['statuses'].values() if status) else "Check Tire Status"
            }
            
            return summary
        except Exception as e:
            return f"Unable to retrieve status summary: {str(e)}"          
def main():
    """Main function with interactive menu"""
    print("FordPass API Python Implementation")
    print("==================================")
    
    # Get credentials
    username = input("Enter your FordPass username: ")
    password = input("Enter your FordPass password: ")
    vin = input("Enter your vehicle VIN: ")
    
    # Create API instance
    ford = FordPassAPI(username, password, vin)
    
    # Main menu
    while True:
        print("\nOptions:")
        print("1. Get vehicle status summary")
        print("2. Get current mileage")
        print("3. Get battery status")
        print("4. Get door and lock status")
        print("5. Get tire status")
        print("6. Get location")
        print("7. Get climate information")
        print("8. Get trip information")
        print("9. Get EV charging status")
        print("0. Exit")
        
        choice = input("\nEnter your choice (0-13): ")
        
        try:
            if choice == "1":
                summary = ford.get_status_summary()
                print("\nVehicle Status Summary:")
                print(json.dumps(summary, indent=2))
                
            elif choice == "2":
                mileage = ford.get_mileage()
                print(f"\n{mileage}")
                
            elif choice == "3":
                battery = ford.get_battery_status()
                print("\nBattery Status:")
                print(json.dumps(battery, indent=2))
                
            elif choice == "4":
                doors = ford.get_door_status()
                print("\nDoor Status:")
                print(json.dumps(doors, indent=2))
                
            elif choice == "5":
                tires = ford.get_tire_status()
                print("\nTire Status:")
                print(json.dumps(tires, indent=2))
                
            elif choice == "6":
                location = ford.get_location()
                print("\nVehicle Location:")
                print(json.dumps(location, indent=2))
                
            elif choice == "7":
                climate = ford.get_climate_status()
                print("\nClimate Information:")
                print(json.dumps(climate, indent=2))
                
            elif choice == "8":
                trip = ford.get_trip_info()
                print("\nTrip Information:")
                print(json.dumps(trip, indent=2))
                
            elif choice == "9":
                charging = ford.get_ev_charging_status()
                print("\nEV Charging Status:")
                print(json.dumps(charging, indent=2))
              
            elif choice == "0":
                print("\nExiting...")
                break
                
            else:
                print("\nInvalid choice. Please try again.")
                
        except Exception as e:
            print(f"\nError: {str(e)}")

if __name__ == "__main__":
    main()
